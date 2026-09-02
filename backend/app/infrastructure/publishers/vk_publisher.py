"""Публикация во VK через API."""

import json
from io import BytesIO

import aiohttp
from loguru import logger
from PIL import Image

from app.core.config import get_settings
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.publishers.base import BasePublisher
from app.utils.text_format import to_vk_text
from app.utils.vk_credentials import resolve_vk_token, resolve_vk_user_token

# У VK лимит текста поста ~16000 символов; берём с запасом.
_VK_MESSAGE_LIMIT = 15000
_VK_WALL_PHOTO_MAX_SIZE = (1280, 1280)


def _prepare_wall_photo_bytes(
    image_bytes: bytes,
    max_size: tuple[int, int] = _VK_WALL_PHOTO_MAX_SIZE,
) -> bytes | None:
    """Нормализует обложку в JPEG для photos.saveWallPhoto.

    VK принимает только валидное изображение; PNG/WebP, переданные как JPEG,
    приводят к ошибке upload/save и fallback в doc (файл на стене).
    """
    if not image_bytes:
        return None
    try:
        img = Image.open(BytesIO(image_bytes))
        img = img.convert("RGB")
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return buffer.getvalue()
    except Exception as exc:
        logger.error("VK wall photo prepare failed", error=str(exc))
        return None


def build_vk_message(post: ProcessedPost, limit: int = _VK_MESSAGE_LIMIT) -> str:
    """Собирает текст поста для VK.

    Для статей (article_body есть) публикуем полный текст — VK допускает
    длинные посты, отдельная страница-ссылка не нужна. Для новостей — анонс.

    Args:
        post: обработанный пост.
        limit: максимум символов.

    Returns:
        str: текст без HTML, обрезанный до лимита по границе предложения.
    """
    raw = post.article_body if post.article_body else post.rewritten_text
    text = to_vk_text(raw or "")
    if len(text) <= limit:
        return text
    truncated = text[: limit - 1].rstrip()
    boundary = max(
        truncated.rfind(". "),
        truncated.rfind(".\n"),
        truncated.rfind("! "),
        truncated.rfind("? "),
        truncated.rfind("?\n"),
    )
    if boundary > limit // 2:
        return truncated[:boundary + 1].rstrip() + "…"
    return truncated + "…"


def _vk_wall_photo_save_fields(upload_data: dict) -> dict[str, str] | None:
    """Нормализует поля ответа upload-сервера для photos.saveWallPhoto."""
    if not all(key in upload_data for key in ("photo", "server", "hash")):
        return None
    photo = upload_data["photo"]
    if isinstance(photo, (list, dict)):
        photo_str = json.dumps(photo, separators=(",", ":"), ensure_ascii=False)
    else:
        photo_str = str(photo)
    return {
        "photo": photo_str,
        "server": str(upload_data["server"]),
        "hash": str(upload_data["hash"]),
    }


class VkPublisher(BasePublisher):
    """Публикует на стену VK."""

    async def publish(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
    ) -> str:
        """Публикует пост на VK.

        Args:
            post: пост.
            channel: канал (platform_id = owner_id сообщества, напр. -240417733).
            image_bytes: статичная обложка (fallback).
            video_bytes: MP4-анимация (приоритет над image).

        Returns:
            str: post_id на платформе.

        Raises:
            RuntimeError: при ошибке или отсутствии токена.
        """
        token = await resolve_vk_token()
        if not token:
            msg = "VK access token not configured (env VK_ACCESS_TOKEN или настройка vk_access_token в БД)"
            raise RuntimeError(msg)

        # Для загрузки фото нужен пользовательский токен с правами photos+wall+groups.
        # Групповые (community) токены блокируются VK с ошибкой 27.
        user_token = await resolve_vk_user_token()
        photo_token = user_token or token

        api_version = get_settings().vk_api_version
        owner_id = channel.platform_id.strip()
        footer = to_vk_text(channel.post_footer or "")
        separator = "\n\n" if footer else ""
        message_limit = _VK_MESSAGE_LIMIT - len(separator) - len(footer)
        message = build_vk_message(post, limit=max(1, message_limit))
        if footer:
            message = f"{message}{separator}{footer}"
        params: dict[str, str | int] = {
            "access_token": token,
            "v": api_version,
            "owner_id": owner_id,
            "message": message,
            "from_group": 1 if owner_id.startswith("-") else 0,
        }

        async with aiohttp.ClientSession() as session:
            attachment = None
            if video_bytes:
                from app.infrastructure.media.gifski_converter import is_gif_bytes

                if is_gif_bytes(video_bytes):
                    attachment = await self._upload_gif_as_doc(
                        session, photo_token, api_version, owner_id, video_bytes
                    )
                    if not attachment:
                        logger.warning(
                            "VK GIF upload failed, falling back to static image",
                            channel_id=channel.id,
                        )
                else:
                    attachment = await self._upload_video(
                        session, photo_token, api_version, owner_id, video_bytes
                    )
                    if not attachment:
                        logger.warning(
                            "VK video upload failed, falling back to static image",
                            channel_id=channel.id,
                        )
            if not attachment and image_bytes:
                attachment = await self._upload_photo(
                    session, photo_token, api_version, owner_id, image_bytes
                )
                # Doc-fallback только без user token — иначе картинка уходит «файлом».
                if not attachment and not user_token:
                    logger.warning(
                        "VK photo upload unavailable without vk_user_token; "
                        "falling back to doc attachment",
                        channel_id=channel.id,
                    )
                    attachment = await self._upload_photo_as_doc(
                        session, token, api_version, owner_id, image_bytes
                    )
                elif not attachment:
                    logger.error(
                        "VK photo upload failed; post will be text-only "
                        "(doc fallback skipped to avoid file attachment)",
                        channel_id=channel.id,
                    )
            if attachment:
                params["attachments"] = attachment

            async with session.post(
                "https://api.vk.com/method/wall.post", data=params
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    error = data["error"]
                    msg = f"VK API error: {error.get('error_msg', error)}"
                    raise RuntimeError(msg)
                post_id = str(data["response"]["post_id"])
                logger.info("VK published", channel_id=channel.id, post_id=post_id)
                return post_id

    async def _upload_video(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_version: str,
        owner_id: str,
        video_bytes: bytes,
    ) -> str | None:
        """Загружает MP4 на стену VK и возвращает attachment video{owner}_{id}."""
        try:
            is_group = owner_id.startswith("-")
            group_id = abs(int(owner_id)) if is_group else None
            save_params: dict[str, str | int] = {
                "access_token": token,
                "v": api_version,
                "name": "cover",
                "wallpost": 0,
            }
            if group_id is not None:
                save_params["group_id"] = group_id
            async with session.get(
                "https://api.vk.com/method/video.save",
                params=save_params,
            ) as resp:
                data = await resp.json()
            if "error" in data:
                err = data["error"]
                logger.error(
                    "VK video.save failed",
                    error_code=err.get("error_code"),
                    error_msg=err.get("error_msg", ""),
                )
                return None
            video_info = data["response"]
            upload_url = video_info.get("upload_url")
            video_owner_id = video_info.get("owner_id")
            video_id = video_info.get("video_id")
            if not upload_url or video_owner_id is None or video_id is None:
                logger.error(
                    "VK video.save missing upload_url or ids",
                    payload=video_info,
                )
                return None

            form = aiohttp.FormData()
            form.add_field(
                "video_file",
                video_bytes,
                filename="cover.mp4",
                content_type="video/mp4",
            )
            async with session.post(str(upload_url), data=form) as upload_resp:
                upload_data = await upload_resp.json(content_type=None)
            if isinstance(upload_data, dict) and not upload_data.get("size"):
                logger.error("VK video upload failed", payload=upload_data)
                return None
            return f"video{video_owner_id}_{video_id}"
        except Exception as exc:
            logger.error("VK video upload failed", error=str(exc))
            return None

    async def _upload_gif_as_doc(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_version: str,
        owner_id: str,
        gif_bytes: bytes,
    ) -> str | None:
        """Загружает GIF как документ стены (автоплей в ленте VK)."""
        try:
            is_group = owner_id.startswith("-")
            group_id = abs(int(owner_id)) if is_group else None

            get_params: dict[str, str | int] = {
                "access_token": token,
                "v": api_version,
                "type": "doc",
            }
            if group_id is not None:
                get_params["group_id"] = group_id
            async with session.get(
                "https://api.vk.com/method/docs.getWallUploadServer",
                params=get_params,
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    err = data["error"]
                    logger.error(
                        "VK docs.getWallUploadServer (gif) failed",
                        error_code=err.get("error_code"),
                        error_msg=err.get("error_msg", ""),
                    )
                    return None
                upload_url = data["response"]["upload_url"]

            form = aiohttp.FormData()
            form.add_field(
                "file",
                gif_bytes,
                filename="cover.gif",
                content_type="image/gif",
            )
            async with session.post(upload_url, data=form) as upload_resp:
                upload_data = await upload_resp.json()

            file_token = upload_data.get("file")
            if not file_token:
                logger.error("VK GIF upload missing file token", payload=upload_data)
                return None

            save_params: dict[str, str | int] = {
                "access_token": token,
                "v": api_version,
                "file": file_token,
                "title": "cover",
            }
            async with session.get(
                "https://api.vk.com/method/docs.save",
                params=save_params,
            ) as save_resp:
                save_data = await save_resp.json()
                if "error" in save_data:
                    err = save_data["error"]
                    logger.error(
                        "VK docs.save (gif) failed",
                        error_code=err.get("error_code"),
                        error_msg=err.get("error_msg", ""),
                    )
                    return None
                doc = save_data["response"]["doc"]
                logger.info("VK GIF uploaded as doc", owner_id=owner_id)
                return f"doc{doc['owner_id']}_{doc['id']}"
        except Exception as exc:
            logger.error("VK GIF upload failed", error=str(exc))
            return None

    async def _save_wall_photo(
        self,
        session: aiohttp.ClientSession,
        save_params: dict[str, str | int],
    ) -> dict | None:
        """Сохраняет загруженное фото на стену (POST FormData, затем GET)."""
        str_params = {key: str(value) for key, value in save_params.items()}
        form = aiohttp.FormData()
        for key, value in str_params.items():
            form.add_field(key, value)

        for method, kwargs in (
            ("POST", {"data": form}),
            ("GET", {"params": str_params}),
        ):
            async with session.request(
                method,
                "https://api.vk.com/method/photos.saveWallPhoto",
                **kwargs,
            ) as save_resp:
                save_data = await save_resp.json()
            if "error" not in save_data:
                return save_data
            err = save_data["error"]
            code = err.get("error_code")
            msg = err.get("error_msg", "")
            logger.warning(
                "VK saveWallPhoto failed method={} error_code={} error_msg={}",
                method,
                code,
                msg,
            )
        return None

    async def _upload_photo(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_version: str,
        owner_id: str,
        image_bytes: bytes,
    ) -> str | None:
        """Загружает фото на стену VK и возвращает attachment-строку.

        Args:
            session: aiohttp-сессия.
            token: VK-токен.
            api_version: версия API.
            owner_id: ID владельца/сообщества (для сообществ — отрицательный).
            image_bytes: JPEG/PNG/WebP — будет нормализовано в JPEG.

        Returns:
            str | None: attachment вида photo{owner}_{id} или None при ошибке.
        """
        try:
            prepared = _prepare_wall_photo_bytes(image_bytes)
            if not prepared:
                return None

            is_group = owner_id.startswith("-")
            group_id = abs(int(owner_id)) if is_group else None

            get_params: dict[str, str | int] = {"access_token": token, "v": api_version}
            if group_id is not None:
                get_params["group_id"] = group_id
            async with session.get(
                "https://api.vk.com/method/photos.getWallUploadServer",
                params=get_params,
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    err = data["error"]
                    error_code = err.get("error_code")
                    error_msg = err.get("error_msg", "")
                    if error_code == 27:
                        logger.error(
                            "VK getWallUploadServer: ошибка 27 — групповой токен не поддерживает photos API. "
                            "Задайте пользовательский токен с правами photos+wall+groups в настройке vk_user_token.",
                            error_code=error_code,
                            error_msg=error_msg,
                        )
                    else:
                        logger.error(
                            "VK getWallUploadServer failed",
                            error_code=error_code,
                            error_msg=error_msg,
                        )
                    return None
                upload_url = data["response"]["upload_url"]

            form = aiohttp.FormData()
            form.add_field(
                "photo", prepared, filename="post.jpg", content_type="image/jpeg"
            )
            async with session.post(upload_url, data=form) as upload_resp:
                upload_data = await upload_resp.json()

            if upload_data.get("error"):
                logger.error(
                    "VK photo upload server returned invalid payload",
                    payload=upload_data,
                )
                return None
            photo_fields = _vk_wall_photo_save_fields(upload_data)
            if not photo_fields:
                logger.error(
                    "VK photo upload server returned invalid payload",
                    payload=upload_data,
                )
                return None

            save_params: dict[str, str | int] = {
                "access_token": token,
                "v": api_version,
                **photo_fields,
            }
            if group_id is not None:
                save_params["group_id"] = group_id

            save_data = await self._save_wall_photo(session, save_params)
            if not save_data:
                return None
            photo = save_data["response"][0]
            return f"photo{photo['owner_id']}_{photo['id']}"
        except Exception as exc:
            logger.error("VK photo upload failed", error=str(exc))
            return None

    async def _upload_photo_as_doc(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_version: str,
        owner_id: str,
        image_bytes: bytes,
    ) -> str | None:
        """Загружает фото как документ — работает с групповым токеном.

        Args:
            session: aiohttp-сессия.
            token: VK групповой токен.
            api_version: версия API.
            owner_id: ID сообщества (отрицательный).
            image_bytes: JPEG.

        Returns:
            str | None: attachment вида doc{owner}_{id} или None при ошибке.
        """
        try:
            is_group = owner_id.startswith("-")
            group_id = abs(int(owner_id)) if is_group else None

            get_params: dict[str, str | int] = {"access_token": token, "v": api_version}
            if group_id is not None:
                get_params["group_id"] = group_id
            async with session.get(
                "https://api.vk.com/method/docs.getWallUploadServer",
                params=get_params,
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    err = data["error"]
                    logger.error(
                        "VK docs.getWallUploadServer failed",
                        error_code=err.get("error_code"),
                        error_msg=err.get("error_msg", ""),
                    )
                    return None
                upload_url = data["response"]["upload_url"]

            prepared = _prepare_wall_photo_bytes(image_bytes)
            if not prepared:
                return None

            form = aiohttp.FormData()
            form.add_field(
                "file", prepared, filename="post.jpg", content_type="image/jpeg"
            )
            async with session.post(upload_url, data=form) as upload_resp:
                upload_data = await upload_resp.json()

            save_params: dict[str, str | int] = {
                "access_token": token,
                "v": api_version,
                "file": upload_data["file"],
                "title": "image",
            }
            async with session.get(
                "https://api.vk.com/method/docs.save",
                params=save_params,
            ) as save_resp:
                save_data = await save_resp.json()
                if "error" in save_data:
                    err = save_data["error"]
                    logger.error(
                        "VK docs.save failed",
                        error_code=err.get("error_code"),
                        error_msg=err.get("error_msg", ""),
                    )
                    return None
                doc = save_data["response"]["doc"]
                logger.info("VK photo uploaded as doc", owner_id=owner_id)
                return f"doc{doc['owner_id']}_{doc['id']}"
        except Exception as exc:
            logger.error("VK doc upload failed", error=str(exc))
            return None
