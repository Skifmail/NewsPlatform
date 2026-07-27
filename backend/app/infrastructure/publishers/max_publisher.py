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
from app.infrastructure.publishers.base import BasePublisher
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
_SEND_ATTEMPTS = 4
_NUMERIC_CHAT_ID_RE = re.compile(r"^-?\d+$")


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
        text = append_post_footer(text, channel.post_footer)

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
    ) -> str:
        """Загружает изображение и возвращает token вложения.

        Args:
            session: HTTP-сессия.
            token: токен бота.
            image_bytes: JPEG/PNG.

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
            filename="post.jpg",
            content_type="image/jpeg",
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
    ) -> str:
        """Отправляет текст и опционально видео или изображение в канал.

        Args:
            session: HTTP-сессия.
            token: токен бота.
            chat_id: ID канала.
            text: HTML-текст.
            image_bytes: статичная обложка (fallback).
            video_bytes: MP4-анимация (приоритет).

        Returns:
            str: message_id.

        Raises:
            RuntimeError: ошибка API.
            PublishPermanentError: ошибка разметки.
        """
        attachments: list[dict[str, Any]] | None = None
        if video_bytes:
            video_token = await cls._upload_video(session, token, video_bytes)
            attachments = [{"type": "video", "payload": {"token": video_token}}]
        elif image_bytes:
            image_token = await cls._upload_image(session, token, image_bytes)
            attachments = [{"type": "image", "payload": {"token": image_token}}]

        body: dict[str, Any] = {
            "text": text,
            "format": "html",
            "notify": True,
        }
        if attachments:
            body["attachments"] = attachments

        last_error: str | None = None
        for attempt in range(1, _SEND_ATTEMPTS + 1):
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
            if error_code == _ATTACHMENT_NOT_READY and attempt < _SEND_ATTEMPTS:
                delay = 0.4 * attempt
                logger.debug(
                    "MAX attachment not ready, retry",
                    attempt=attempt,
                    delay=delay,
                )
                await asyncio.sleep(delay)
                last_error = cls._format_api_error(payload, "send message")
                continue

            if resp.status == 400 and "format" in str(payload.get("message", "")).lower():
                raise PublishPermanentError(
                    cls._format_api_error(payload, "send message")
                )

            msg = cls._format_api_error(payload, "send message")
            raise RuntimeError(msg)

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
