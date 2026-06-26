"""Telegram парсер через Telethon."""

from datetime import UTC, datetime

from loguru import logger
from telethon import TelegramClient
from app.core.config import get_settings
from app.domain.entities import RawPostDTO
from app.infrastructure.models.source import Source
from app.infrastructure.parsers.base import BaseParser

SESSION_PATH = "telethon_sessions/session"


class TelegramParser(BaseParser):
    """Читает публичные каналы через userbot."""

    async def fetch_new(self, source: Source) -> list[RawPostDTO]:
        """Загружает последние сообщения канала.

        Args:
            source: источник (url = @channel или t.me/...).

        Returns:
            list[RawPostDTO]: сообщения.
        """
        settings = get_settings()
        if not settings.telegram_api_id or not settings.telegram_api_hash:
            logger.warning("Telethon credentials not configured")
            return []

        channel = source.url.replace("https://t.me/", "@").lstrip("@")
        if not channel.startswith("@"):
            channel = f"@{channel}"

        posts: list[RawPostDTO] = []
        client = TelegramClient(
            SESSION_PATH,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        await client.start(phone=settings.telegram_phone or None)
        try:
            entity = await client.get_entity(channel)
            async for message in client.iter_messages(entity, limit=30):
                if not message.text:
                    continue
                image_url = None
                if message.photo:
                    image_url = f"telegram://{message.id}"

                posts.append(
                    RawPostDTO(
                        external_id=str(message.id),
                        title=None,
                        content=message.text,
                        url=f"https://t.me/{channel.lstrip('@')}/{message.id}",
                        image_url=image_url,
                        topic=source.topic,
                        published_at=message.date.replace(tzinfo=UTC)
                        if message.date
                        else None,
                    )
                )
        finally:
            await client.disconnect()

        logger.info("Telegram fetched", source_id=source.id, count=len(posts))
        return posts
