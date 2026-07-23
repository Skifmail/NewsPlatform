"""Публикация во VK через API."""

import aiohttp
from loguru import logger

from app.core.config import get_settings
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.publishers.base import BasePublisher
from app.utils.text_format import strip_html_tags
from app.utils.vk_credentials import resolve_vk_token, resolve_vk_user_token

# У VK лимит текста поста ~16000 символов; берём с запасом.
_VK_MESSAGE_LIMIT = 15000


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
    text = strip_html_tags(raw or "")
    if len(text) <= limit:
        return text
    truncated = text[:limit]
    boundary = max(
        truncated.rfind(". "),
        truncated.rfind(".\n"),
        truncated.rfind("! "),
        truncated.rfind("? "),
        truncated.rfind("?\n"),
    )
    if boundary > limit // 2:
        return truncated[:boundary + 1] + "…"
    return truncated.rstrip() + "…"


class VkPublisher(BasePublisher):
    """Публикует на стену VK."""

    async def publish(
        self, post: ProcessedPost, channel: Channel, image_bytes: bytes | None
    ) -> str:
        """Публикует пост на VK.

        Args:
            post: пост.
            channel: канал (platform_id = owner_id сообщества, напр. -240417733).
            image_bytes: картинка (опционально).

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
        params: dict[str, str | int] = {
            "access_token": token,
            "v": api_version,
            "owner_id": owner_id,
            "message": build_vk_message(post),
            "from_group": 1 if owner_id.startswith("-") else 0,
        }

        async with aiohttp.ClientSession() as session:
            if image_bytes:
                attachment = await self._upload_photo(
                    session, photo_token, api_version, owner_id, image_bytes
                )
                if not attachment:
                    # Фоллбэк: docs API работает с групповым токеном (без ошибки 27)
                    attachment = await self._upload_photo_as_doc(
                        session, token, api_version, owner_id, image_bytes
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
            image_bytes: JPEG.

        Returns:
            str | None: attachment вида photo{owner}_{id} или None при ошибке.
        """
        try:
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
                "photo", image_bytes, filename="post.jpg", content_type="image/jpeg"
            )
            async with session.post(upload_url, data=form) as upload_resp:
                upload_data = await upload_resp.json()

            save_params: dict[str, str | int] = {
                "access_token": token,
                "v": api_version,
                "photo": upload_data["photo"],
                "server": upload_data["server"],
                "hash": upload_data["hash"],
            }
            if group_id is not None:
                save_params["group_id"] = group_id
            async with session.get(
                "https://api.vk.com/method/photos.saveWallPhoto", params=save_params
            ) as save_resp:
                save_data = await save_resp.json()
                if "error" in save_data:
                    err = save_data["error"]
                    logger.error(
                        "VK saveWallPhoto failed",
                        error_code=err.get("error_code"),
                        error_msg=err.get("error_msg", ""),
                    )
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

            form = aiohttp.FormData()
            form.add_field(
                "file", image_bytes, filename="post.jpg", content_type="image/jpeg"
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
