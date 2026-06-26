"""Публикация во VK через API."""

import aiohttp
from loguru import logger

from app.core.config import get_settings
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.publishers.base import BasePublisher
from app.utils.text_format import strip_html_tags


class VkPublisher(BasePublisher):
    """Публикует на стену VK."""

    async def publish(
        self, post: ProcessedPost, channel: Channel, image_bytes: bytes | None
    ) -> str:
        """Публикует пост на VK.

        Args:
            post: пост.
            channel: канал (platform_id = owner_id или group id).
            image_bytes: картинка (опционально).

        Returns:
            str: post_id на платформе.

        Raises:
            RuntimeError: при ошибке.
        """
        settings = get_settings()
        if not settings.vk_access_token:
            msg = "VK_ACCESS_TOKEN not configured"
            raise RuntimeError(msg)

        owner_id = channel.platform_id
        params: dict[str, str | int] = {
            "access_token": settings.vk_access_token,
            "v": settings.vk_api_version,
            "owner_id": owner_id,
            "message": strip_html_tags(post.rewritten_text),
            "from_group": 1 if owner_id.startswith("-") else 0,
        }

        api_url = "https://api.vk.com/method/wall.post"

        async with aiohttp.ClientSession() as session:
            if image_bytes:
                attachment = await self._upload_photo(
                    session, settings.vk_access_token, owner_id, image_bytes
                )
                if attachment:
                    params["attachments"] = attachment

            async with session.post(api_url, data=params) as resp:
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
        owner_id: str,
        image_bytes: bytes,
    ) -> str | None:
        """Загружает фото на стену VK.

        Args:
            session: aiohttp сессия.
            token: токен.
            owner_id: ID владельца/группы.
            image_bytes: JPEG.

        Returns:
            str | None: attachment string.
        """
        try:
            upload_url_params = {
                "access_token": token,
                "v": settings.vk_api_version,
                "group_id": abs(int(owner_id)) if owner_id.startswith("-") else None,
            }
            if not owner_id.startswith("-"):
                upload_url_params = {
                    "access_token": token,
                    "v": settings.vk_api_version,
                }
            method = (
                "photos.getWallUploadServer"
                if owner_id.startswith("-")
                else "photos.getWallUploadServer"
            )
            async with session.get(
                f"https://api.vk.com/method/{method}",
                params={k: v for k, v in upload_url_params.items() if v is not None},
            ) as resp:
                data = await resp.json()
                if "error" in data:
                    return None
                upload_url = data["response"]["upload_url"]

            form = aiohttp.FormData()
            form.add_field(
                "photo", image_bytes, filename="post.jpg", content_type="image/jpeg"
            )
            async with session.post(upload_url, data=form) as upload_resp:
                upload_data = await upload_resp.json()

            save_params = {
                "access_token": token,
                "v": settings.vk_api_version,
                "photo": upload_data["photo"],
                "server": upload_data["server"],
                "hash": upload_data["hash"],
                "group_id": abs(int(owner_id)) if owner_id.startswith("-") else None,
            }
            async with session.get(
                "https://api.vk.com/method/photos.saveWallPhoto",
                params={k: v for k, v in save_params.items() if v is not None},
            ) as save_resp:
                save_data = await save_resp.json()
                if "error" in save_data:
                    return None
                photo = save_data["response"][0]
                return f"photo{photo['owner_id']}_{photo['id']}"
        except Exception as exc:
            logger.warning("VK photo upload failed", error=str(exc))
            return None
