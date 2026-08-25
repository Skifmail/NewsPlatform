"""Публикация в каналы MAX через Bot API."""

from __future__ import annotations

import asyncio
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

import aiohttp
from loguru import logger

from app.core.config import get_settings
from app.domain.enums import ContentMode
from app.domain.publish import PublishPermanentError
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.domain.article_meta import parse_article_meta, serialize_article_meta
from app.infrastructure.publishers.base import BasePublisher
from app.infrastructure.publishers.max_keyboard import build_callback_keyboard
from app.infrastructure.publishers.max_video_token_cache import (
    clear_cached_max_video_token,
    get_cached_max_video_token,
    set_cached_max_video_token,
)
from app.infrastructure.publishers.telegraph_publisher import TelegraphPublisher
from app.utils.max_api import get_max_api_base, max_client_session
from app.utils.telegram_channels import is_long_form_article_channel
from app.utils.text_format import (
    MAX_MESSAGE_MAX,
    append_post_footer,
    build_article_read_more_html,
    build_article_telegram_text,
    to_max_api_html,
)

_ATTACHMENT_NOT_READY = "attachment.not.ready"
# Картинка обычно готова сразу; видео MAX обрабатывает асинхронно —
# для роликов ~100–250 МБ нужно несколько минут (см. dev.max.ru uploads).
_SEND_ATTEMPTS = 4
_SEND_ATTEMPTS_WITH_VIDEO = 12
_SEND_ATTEMPTS_LARGE_VIDEO = 30
_VIDEO_READY_INITIAL_DELAY = 8.0
_NUMERIC_CHAT_ID_RE = re.compile(r"^-?\d+$")


def _video_size_mb(video_bytes: bytes | None) -> float:
    """Размер видео в мегабайтах."""
    if not video_bytes:
        return 0.0
    return len(video_bytes) / (1024 * 1024)


def _video_initial_delay(video_bytes: bytes | None) -> float:
    """Пауза после upload перед первой отправкой (зависит от размера)."""
    mb = _video_size_mb(video_bytes)
    if mb <= 0:
        return 0.0
    # ~0.7 с на МБ: 30 МБ ≈ 21 с, 200 МБ ≈ 140 с (потолок 180 с).
    return min(180.0, max(_VIDEO_READY_INITIAL_DELAY, mb * 0.7))


def _video_send_attempts(video_bytes: bytes | None) -> int:
    """Число попыток POST /messages при наличии видео."""
    mb = _video_size_mb(video_bytes)
    if mb >= 40:
        return _SEND_ATTEMPTS_LARGE_VIDEO
    if mb > 0:
        return _SEND_ATTEMPTS_WITH_VIDEO
    return _SEND_ATTEMPTS


def _attachment_retry_delay(attempt: int, *, has_video: bool) -> float:
    """Пауза перед повтором send при attachment.not.ready.

    Args:
        attempt: номер попытки (1-based).
        has_video: в сообщении есть video-вложение.

    Returns:
        float: секунды ожидания.
    """
    if has_video:
        # 2, 3, 4.5… с потолком 30 с
        return min(30.0, 2.0 * (1.5 ** (attempt - 1)))
    return 0.4 * attempt


class MaxPublisher(BasePublisher):
    """Публикует посты в канал MAX (Bot API platform-api.max.ru)."""

    async def publish(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
    ) -> str:
        """Отправляет сообщение в канал MAX.

        Args:
            post: пост.
            channel: канал (``platform_id`` = ``chat_id`` или публичная ссылка).
            image_bytes: статичная обложка (fallback).
            video_bytes: анимированная обложка MP4 (приоритет над image).

        Returns:
            str: ID сообщения на платформе.

        Raises:
            RuntimeError: при ошибке API или отсутствии токена.
            PublishPermanentError: при ошибке разметки или неверном chat_id.
        """
        if post.content_mode == ContentMode.ARTICLE.value:
            return await self._publish_article(post, channel, image_bytes, video_bytes=video_bytes)

        settings = get_settings()
        if not settings.max_bot_token:
            msg = "MAX_BOT_TOKEN not configured"
            raise RuntimeError(msg)

        text = append_post_footer(to_max_api_html(post.rewritten_text), channel.post_footer)
        keyboard = None
        meta = parse_article_meta(post.article_meta)
        if meta.button_options:
            keyboard = build_callback_keyboard(
                meta.button_options,
                payload_prefix=f"pq:{post.id}",
            )
        async with max_client_session() as session:
            chat_id = await self._resolve_chat_id(
                session, settings.max_bot_token, channel.platform_id
            )
            message_id = await self._send_message(
                session,
                settings.max_bot_token,
                chat_id,
                text,
                image_bytes,
                video_bytes=video_bytes,
                extra_attachments=[keyboard] if keyboard else None,
                post=post,
            )
            logger.info(
                "MAX published",
                channel_id=channel.id,
                chat_id=chat_id,
                message_id=message_id,
            )
            return message_id

    async def _publish_article(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        *,
        video_bytes: bytes | None = None,
    ) -> str:
        """Публикует статью: целиком (long-form) или анонс со ссылкой на Telegraph.

        Для long-form каналов (ПАРАГРАФ, Github) текст уходит одним сообщением,
        потому что Telegraph недоступен без VPN, а MAX-аудитория читает без него.

        Args:
            post: пост в режиме article.
            channel: канал MAX.
            image_bytes: обложка.

        Returns:
            str: ID сообщения.

        Raises:
            RuntimeError: при ошибке API.
        """
        if is_long_form_article_channel(channel):
            return await self._publish_long_form_article(
                post, channel, image_bytes, video_bytes=video_bytes
            )
        return await self._publish_telegraph_article(
            post, channel, image_bytes, video_bytes=video_bytes
        )

    async def _publish_long_form_article(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        *,
        video_bytes: bytes | None = None,
    ) -> str:
        """Публикует статью целиком в MAX без Telegraph.

        Args:
            post: пост в режиме article.
            channel: канал MAX.
            image_bytes: обложка.

        Returns:
            str: ID сообщения.

        Raises:
            RuntimeError: при ошибке API или отсутствии токена.
        """
        settings = get_settings()
        if not settings.max_bot_token:
            msg = "MAX_BOT_TOKEN not configured"
            raise RuntimeError(msg)
        if not post.article_body and not post.rewritten_text:
            msg = "Article body is empty"
            raise RuntimeError(msg)

        text = build_article_telegram_text(
            article_title=post.article_title,
            teaser_html=post.rewritten_text,
            body_html=post.article_body,
            max_length=MAX_MESSAGE_MAX,
        )
        text = append_post_footer(to_max_api_html(text), channel.post_footer)

        keyboard = None
        meta = parse_article_meta(post.article_meta)
        if meta.button_options:
            keyboard = build_callback_keyboard(
                meta.button_options,
                payload_prefix=f"pq:{post.id}",
            )

        async with max_client_session() as session:
            chat_id = await self._resolve_chat_id(
                session, settings.max_bot_token, channel.platform_id
            )
            message_id = await self._send_message(
                session,
                settings.max_bot_token,
                chat_id,
                text,
                image_bytes,
                video_bytes=video_bytes,
                extra_attachments=[keyboard] if keyboard else None,
                post=post,
            )
            logger.info(
                "MAX long-form article published",
                channel_id=channel.id,
                chat_id=chat_id,
                message_id=message_id,
                text_length=len(text),
            )
            return message_id

    async def _publish_telegraph_article(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        *,
        video_bytes: bytes | None = None,
    ) -> str:
        """Публикует анонс статьи со ссылкой на Telegraph.

        Args:
            post: пост в режиме article.
            channel: канал MAX.
            image_bytes: обложка.

        Returns:
            str: ID сообщения.

        Raises:
            RuntimeError: при ошибке API.
        """
        settings = get_settings()
        if not settings.max_bot_token:
            msg = "MAX_BOT_TOKEN not configured"
            raise RuntimeError(msg)
        if not post.article_body:
            msg = "Article body is empty"
            raise RuntimeError(msg)

        telegraph = TelegraphPublisher()
        telegraph_url = post.telegraph_url
        title = (post.article_title or "Статья").strip()
        if not telegraph_url:
            telegraph_url = await telegraph.create_page(
                title,
                post.article_body,
                author_name=channel.name,
            )
            post.telegraph_url = telegraph_url
        else:
            await telegraph.set_author_name(
                telegraph_url,
                channel.name,
                title=title,
            )

        teaser = to_max_api_html(post.rewritten_text.strip())
        link = build_article_read_more_html(
            telegraph_url,
            channel_name=channel.name,
            article_title=title,
            article_body=post.article_body or "",
            post_id=post.id,
        )
        text = append_post_footer(f"{teaser}\n\n{link}".strip(), channel.post_footer)

        async with max_client_session() as session:
            chat_id = await self._resolve_chat_id(
                session, settings.max_bot_token, channel.platform_id
            )
            message_id = await self._send_message(
                session,
                settings.max_bot_token,
                chat_id,
                text,
                image_bytes,
                video_bytes=video_bytes,
                post=post,
            )
            logger.info(
                "MAX article teaser published",
                channel_id=channel.id,
                chat_id=chat_id,
                message_id=message_id,
                telegraph_url=telegraph_url,
            )
            return message_id

    @staticmethod
    def _auth_headers(token: str) -> dict[str, str]:
        """Собирает заголовок авторизации MAX API.

        Args:
            token: токен бота.

        Returns:
            dict[str, str]: заголовки HTTP.
        """
        return {"Authorization": token}

    @staticmethod
    def _normalize_chat_link(platform_id: str) -> str:
        """Извлекает slug канала из ссылки или @username.

        Args:
            platform_id: значение из поля канала.

        Returns:
            str: slug для GET /chats/{chatLink}.
        """
        stripped = platform_id.strip()
        if "max.ru/" in stripped.lower():
            path = urlparse(stripped).path.strip("/")
            return path.split("/")[-1]
        if stripped.startswith("@"):
            return stripped[1:]
        return stripped

    @classmethod
    async def _resolve_chat_id(
        cls,
        session: aiohttp.ClientSession,
        token: str,
        platform_id: str,
    ) -> int:
        """Определяет числовой chat_id канала.

        Args:
            session: HTTP-сессия.
            token: токен бота.
            platform_id: chat_id или публичная ссылка/slug канала.

        Returns:
            int: chat_id для POST /messages.

        Raises:
            PublishPermanentError: канал не найден или бот не добавлен.
            RuntimeError: ошибка API.
        """
        raw = platform_id.strip()
        if _NUMERIC_CHAT_ID_RE.fullmatch(raw):
            return int(raw)

        link = cls._normalize_chat_link(raw)
        url = f"{get_max_api_base()}/chats/{link}"
        async with session.get(url, headers=cls._auth_headers(token)) as resp:
            payload = await cls._read_json(resp)
        if resp.status == 404:
            code = str(payload.get("code", ""))
            msg = (
                f"MAX channel not found for link '{link}'"
                + (f" ({code})" if code else "")
                + ". Для приватного канала укажите числовой chat_id "
                "(из web.max.ru или через событие bot_added после добавления бота)."
            )
            raise PublishPermanentError(msg)
        cls._raise_for_api_error(resp.status, payload, context="resolve chat_id")

        chat_id = payload.get("chat_id")
        if chat_id is None:
            msg = f"MAX API did not return chat_id for link '{link}'"
            raise RuntimeError(msg)
        return int(chat_id)

    @classmethod
    async def _upload_image(
        cls,
        session: aiohttp.ClientSession,
        token: str,
        image_bytes: bytes,
        *,
        filename: str = "post.jpg",
        content_type: str = "image/jpeg",
    ) -> str:
        """Загружает изображение и возвращает token вложения.

        Args:
            session: HTTP-сессия.
            token: токен бота.
            image_bytes: JPEG/PNG/GIF.
            filename: имя файла при upload.
            content_type: MIME-тип.

        Returns:
            str: token для attachments в POST /messages.

        Raises:
            RuntimeError: ошибка загрузки.
        """
        async with session.post(
            f"{get_max_api_base()}/uploads",
            params={"type": "image"},
            headers=cls._auth_headers(token),
        ) as resp:
            meta = await cls._read_json(resp)
        cls._raise_for_api_error(resp.status, meta, context="uploads")

        upload_url = meta.get("url")
        if not isinstance(upload_url, str) or not upload_url:
            msg = "MAX uploads response missing url"
            raise RuntimeError(msg)

        form = aiohttp.FormData()
        form.add_field(
            "data",
            image_bytes,
            filename=filename,
            content_type=content_type,
        )
        async with session.post(upload_url, data=form) as upload_resp:
            upload_payload = await cls._read_json(upload_resp)
        if upload_resp.status >= 400:
            msg = cls._format_api_error(upload_payload, "image upload")
            raise RuntimeError(msg)

        upload_token = cls._extract_upload_token(upload_payload, upload_url)
        if upload_token:
            return upload_token

        logger.warning(
            "MAX image upload unexpected payload",
            status=upload_resp.status,
            keys=list(upload_payload.keys()),
        )
        msg = "MAX image upload did not return token"
        raise RuntimeError(msg)


    @classmethod
    async def _upload_video(
        cls,
        session: aiohttp.ClientSession,
        token: str,
        video_bytes: bytes,
    ) -> str:
        """Загружает MP4 и возвращает token вложения type=video."""
        async with session.post(
            f"{get_max_api_base()}/uploads",
            params={"type": "video"},
            headers=cls._auth_headers(token),
        ) as resp:
            meta = await cls._read_json(resp)
        cls._raise_for_api_error(resp.status, meta, context="uploads")

        upload_url = meta.get("url")
        video_token = meta.get("token")
        if not isinstance(upload_url, str) or not upload_url:
            msg = "MAX uploads response missing url"
            raise RuntimeError(msg)
        if not isinstance(video_token, str) or not video_token:
            msg = "MAX video uploads response missing token"
            raise RuntimeError(msg)

        form = aiohttp.FormData()
        form.add_field(
            "data",
            video_bytes,
            filename="cover.mp4",
            content_type="video/mp4",
        )
        async with session.post(upload_url, data=form) as upload_resp:
            upload_payload = await cls._read_json(upload_resp)
        if upload_resp.status >= 400:
            msg = cls._format_api_error(upload_payload, "video upload")
            raise RuntimeError(msg)

        return video_token

    @staticmethod
    def _persist_video_token(
        post: ProcessedPost | None,
        video_token: str,
        video_source: str | None,
    ) -> None:
        """Пишет token в article_meta поста и Redis (для повторов без upload)."""
        if video_source:
            set_cached_max_video_token(video_source, video_token)
        if post is None or not video_source:
            return
        meta = parse_article_meta(post.article_meta)
        meta.max_video_token = video_token
        meta.max_video_source = video_source
        post.article_meta = serialize_article_meta(meta)

    @classmethod
    async def _get_video_info(
        cls,
        session: aiohttp.ClientSession,
        token: str,
        video_token: str,
    ) -> dict[str, Any] | None:
        """GET /videos/{token} — статус обработки ролика."""
        async with session.get(
            f"{get_max_api_base()}/videos/{video_token}",
            headers=cls._auth_headers(token),
        ) as resp:
            if resp.status == 404:
                return None
            payload = await cls._read_json(resp)
            if resp.status >= 400:
                logger.warning(
                    "MAX GET /videos failed",
                    status=resp.status,
                    payload=payload,
                )
                return None
            return payload if isinstance(payload, dict) else None

    @classmethod
    def _video_info_ready(cls, info: dict[str, Any] | None) -> bool:
        """Видео готово к attach, если есть mp4 URL в ответе GET /videos."""
        if not info:
            return False
        urls = info.get("urls")
        if not isinstance(urls, dict) or not urls:
            return False
        return any(str(key).startswith("mp4") for key in urls)

    @classmethod
    async def _wait_video_ready(
        cls,
        session: aiohttp.ClientSession,
        token: str,
        video_token: str,
        *,
        size_hint_bytes: int = 0,
    ) -> bool:
        """Ждёт, пока MAX обработает видео (опрос GET /videos/{token})."""
        mb = size_hint_bytes / (1024 * 1024) if size_hint_bytes else 0.0
        # 200 МБ → до ~15 мин опроса; мелкие ролики — быстрее.
        timeout = min(900.0, max(90.0, mb * 4.0)) if mb else 120.0
        poll = 5.0 if mb >= 40 else 2.5
        deadline = asyncio.get_event_loop().time() + timeout
        attempt = 0
        while asyncio.get_event_loop().time() < deadline:
            attempt += 1
            info = await cls._get_video_info(session, token, video_token)
            if info is None:
                logger.warning(
                    "MAX video token missing on GET /videos",
                    attempt=attempt,
                )
                return False
            if cls._video_info_ready(info):
                logger.info(
                    "MAX video ready",
                    attempt=attempt,
                    duration=info.get("duration"),
                    width=info.get("width"),
                    url_keys=list((info.get("urls") or {}).keys())[:6],
                )
                return True
            logger.info(
                "MAX video still processing",
                attempt=attempt,
                duration=info.get("duration"),
                width=info.get("width"),
            )
            await asyncio.sleep(poll)
        return False

    @classmethod
    async def _resolve_video_token(
        cls,
        session: aiohttp.ClientSession,
        token: str,
        *,
        post: ProcessedPost | None,
        video_bytes: bytes | None,
    ) -> tuple[str | None, int]:
        """Возвращает (token, size_hint) — с кэша или после upload.

        Returns:
            tuple: token и размер байт для расчёта таймаута (0 если неизвестен).
        """
        video_source = post.generated_video_url if post else None
        size_hint = len(video_bytes) if video_bytes else 0

        candidates: list[str] = []
        if post:
            meta = parse_article_meta(post.article_meta)
            if (
                meta.max_video_token
                and meta.max_video_source == video_source
                and meta.max_video_token.strip()
            ):
                candidates.append(meta.max_video_token.strip())
        cached = get_cached_max_video_token(video_source)
        if cached and cached not in candidates:
            candidates.append(cached)

        for candidate in candidates:
            info = await cls._get_video_info(session, token, candidate)
            if info is None:
                clear_cached_max_video_token(video_source)
                continue
            logger.info("MAX reusing cached video token", source=video_source)
            cls._persist_video_token(post, candidate, video_source)
            return candidate, size_hint

        if not video_bytes:
            return None, 0

        from app.infrastructure.media.gifski_converter import is_gif_bytes
        from app.infrastructure.media.max_video_transcode import prepare_video_for_max

        if is_gif_bytes(video_bytes):
            return None, size_hint

        # Крупные ролики (~100–200 МБ) MAX не успевает обработать →
        # video.not.processed. Сжимаем до ~720p перед upload.
        upload_bytes = prepare_video_for_max(video_bytes)
        size_hint = len(upload_bytes)
        video_token = await cls._upload_video(session, token, upload_bytes)
        cls._persist_video_token(post, video_token, video_source)
        logger.info(
            "MAX video uploaded",
            size_mb=round(size_hint / (1024 * 1024), 1) if size_hint else 0,
            source=video_source,
        )
        return video_token, size_hint

    @staticmethod
    def _extract_upload_token(
        upload_payload: dict[str, Any],
        upload_url: str,
    ) -> str | None:
        """Извлекает token вложения из ответа upload-сервера MAX.

        Для ``type=image`` token приходит в ``photos.{photoId}.token``,
        для video/audio — в корне ``token``.

        Args:
            upload_payload: JSON после POST на upload URL.
            upload_url: URL загрузки из POST /uploads.

        Returns:
            str | None: token для attachments или None.
        """
        top_level = upload_payload.get("token")
        if isinstance(top_level, str) and top_level:
            return top_level

        photos = upload_payload.get("photos")
        if isinstance(photos, dict):
            for photo_data in photos.values():
                if not isinstance(photo_data, dict):
                    continue
                nested = photo_data.get("token")
                if isinstance(nested, str) and nested:
                    return nested

        query_token = parse_qs(urlparse(upload_url).query).get("token", [None])[0]
        if isinstance(query_token, str) and query_token:
            return query_token

        return None

    @classmethod
    async def _send_message(
        cls,
        session: aiohttp.ClientSession,
        token: str,
        chat_id: int,
        text: str,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
        extra_attachments: list[dict[str, Any]] | None = None,
        post: ProcessedPost | None = None,
    ) -> str:
        """Отправляет текст и опционально видео или изображение в канал.

        Видео: token кэшируется (article_meta + Redis). Повтор публикации
        не заливает файл заново — ждёт GET /videos/{token} и шлёт сообщение.

        Args:
            session: HTTP-сессия.
            token: токен бота.
            chat_id: ID канала.
            text: HTML-текст.
            image_bytes: статичная обложка.
            video_bytes: MP4 (или None, если token уже в кэше поста).
            extra_attachments: клавиатура и пр.
            post: для чтения/записи max_video_token.

        Returns:
            str: message_id.

        Raises:
            RuntimeError: ошибка API.
            PublishPermanentError: ошибка разметки / видео не готово.
        """
        attachments: list[dict[str, Any]] = []
        if image_bytes:
            image_token = await cls._upload_image(session, token, image_bytes)
            attachments.append({"type": "image", "payload": {"token": image_token}})

        video_token: str | None = None
        size_hint = len(video_bytes) if video_bytes else 0
        if video_bytes or (
            post
            and post.generated_video_url
            and (
                parse_article_meta(post.article_meta).max_video_token
                or get_cached_max_video_token(post.generated_video_url)
            )
        ):
            from app.infrastructure.media.gifski_converter import is_gif_bytes

            if video_bytes and is_gif_bytes(video_bytes):
                logger.warning(
                    "MAX received GIF animation; clients may show a still frame"
                )
                if not image_bytes:
                    gif_token = await cls._upload_image(
                        session,
                        token,
                        video_bytes,
                        filename="cover.gif",
                        content_type="image/gif",
                    )
                    attachments.append(
                        {"type": "image", "payload": {"token": gif_token}}
                    )
            else:
                video_token, size_hint = await cls._resolve_video_token(
                    session,
                    token,
                    post=post,
                    video_bytes=video_bytes,
                )
                if video_token:
                    ready = await cls._wait_video_ready(
                        session,
                        token,
                        video_token,
                        size_hint_bytes=size_hint,
                    )
                    if not ready:
                        raise PublishPermanentError(
                            "MAX ещё обрабатывает видео. Токен сохранён — "
                            "нажмите «Опубликовать» снова через пару минут "
                            "(повторная заливка файла не нужна)."
                        )
                    attachments.append(
                        {"type": "video", "payload": {"token": video_token}}
                    )

        body: dict[str, Any] = {
            "text": text,
            "format": "html",
            "notify": True,
        }
        if extra_attachments:
            attachments = attachments + list(extra_attachments)
        if attachments:
            body["attachments"] = attachments

        has_video = any(a.get("type") == "video" for a in attachments)
        max_attempts = (
            _video_send_attempts(b"x" * size_hint)
            if has_video and size_hint
            else (_SEND_ATTEMPTS_WITH_VIDEO if has_video else _SEND_ATTEMPTS)
        )

        last_error: str | None = None
        dropped_cover = False
        for attempt in range(1, max_attempts + 1):
            if (
                has_video
                and not dropped_cover
                and attempt > max(3, max_attempts // 2)
                and any(a.get("type") == "image" for a in body.get("attachments", []))
            ):
                body["attachments"] = [
                    a
                    for a in body["attachments"]
                    if a.get("type") != "image"
                ]
                dropped_cover = True
                logger.warning(
                    "MAX dropping cover image; retrying with video only",
                    attempt=attempt,
                )

            async with session.post(
                f"{get_max_api_base()}/messages",
                params={"chat_id": chat_id},
                headers={**cls._auth_headers(token), "Content-Type": "application/json"},
                json=body,
            ) as resp:
                payload = await cls._read_json(resp)

            if resp.status < 400:
                message_id = cls._extract_message_id(payload)
                if message_id:
                    return message_id
                msg = "MAX API response missing message id"
                raise RuntimeError(msg)

            error_code = str(payload.get("code", ""))
            if error_code == _ATTACHMENT_NOT_READY and attempt < max_attempts:
                delay = _attachment_retry_delay(attempt, has_video=has_video)
                logger.info(
                    "MAX attachment not ready, retry",
                    attempt=attempt,
                    max_attempts=max_attempts,
                    delay=delay,
                    has_video=has_video,
                    dropped_cover=dropped_cover,
                )
                await asyncio.sleep(delay)
                last_error = cls._format_api_error(payload, "send message")
                continue

            if resp.status == 400 and "format" in str(payload.get("message", "")).lower():
                raise PublishPermanentError(
                    cls._format_api_error(payload, "send message")
                )

            if error_code == _ATTACHMENT_NOT_READY:
                raise PublishPermanentError(
                    (last_error or cls._format_api_error(payload, "send message"))
                    + ". Токен видео сохранён — повторите публикацию позже без повторной заливки."
                )

            msg = cls._format_api_error(payload, "send message")
            raise RuntimeError(msg)

        if has_video:
            raise PublishPermanentError(
                (last_error or "MAX video attachment not ready")
                + ". Токен видео сохранён — повторите публикацию позже без повторной заливки."
            )
        msg = last_error or "MAX send message failed after retries"
        raise RuntimeError(msg)

    @staticmethod
    async def _read_json(resp: aiohttp.ClientResponse) -> dict[str, Any]:
        """Безопасно читает JSON-ответ MAX API.

        Args:
            resp: HTTP-ответ.

        Returns:
            dict[str, Any]: тело ответа или пустой словарь.
        """
        try:
            data = await resp.json(content_type=None)
        except (aiohttp.ContentTypeError, ValueError):
            return {}
        if isinstance(data, dict):
            return data
        return {}

    @staticmethod
    def _format_api_error(payload: dict[str, Any], context: str) -> str:
        """Форматирует ошибку MAX API.

        Args:
            payload: JSON ответа.
            context: контекст операции.

        Returns:
            str: текст ошибки.
        """
        code = payload.get("code")
        message = payload.get("message") or payload.get("error")
        if code and message:
            return f"MAX {context} error [{code}]: {message}"
        if message:
            return f"MAX {context} error: {message}"
        return f"MAX {context} failed"

    @classmethod
    def _raise_for_api_error(
        cls,
        status: int,
        payload: dict[str, Any],
        *,
        context: str,
    ) -> None:
        """Поднимает исключение при HTTP-ошибке MAX API.

        Args:
            status: HTTP-код.
            payload: JSON ответа.
            context: контекст операции.

        Raises:
            RuntimeError: при status >= 400.
        """
        if status < 400:
            return
        raise RuntimeError(cls._format_api_error(payload, context))

    @staticmethod
    def _extract_message_id(payload: dict[str, Any]) -> str | None:
        """Извлекает ID отправленного сообщения из ответа API.

        Args:
            payload: JSON ответа POST /messages.

        Returns:
            str | None: ID сообщения, если найден.
        """
        message = payload.get("message")
        if not isinstance(message, dict):
            return None
        for key in ("message_id", "mid", "id"):
            value = message.get(key)
            if value is not None:
                return str(value)
        body = message.get("body")
        if isinstance(body, dict):
            for key in ("mid", "message_id", "id"):
                value = body.get(key)
                if value is not None:
                    return str(value)
        return None
