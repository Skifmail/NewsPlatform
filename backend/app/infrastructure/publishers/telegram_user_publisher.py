"""Публикация в Telegram через Telethon (userbot, MTProto).

Позволяет подписи к медиа до ``TELEGRAM_USER_CAPTION_MAX`` (4096) при Premium
на аккаунте сессии. Бот API ограничен 1024 символами.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from loguru import logger
from telethon import TelegramClient
from telethon.errors import (
    ChatWriteForbiddenError,
    FloodWaitError,
    RPCError,
    UserNotParticipantError,
)

from app.core.config import get_settings
from app.infrastructure.parsers.telegram_parser import SESSION_PATH
from app.infrastructure.stats.telegram_stats import (
    _is_numeric_chat_id,
    _normalize_telegram_channel,
)
from app.infrastructure.stats.telethon_lock import TelethonSessionBusyError, telethon_session_lock
from app.utils.text_format import TELEGRAM_USER_CAPTION_MAX, to_telethon_html

if TYPE_CHECKING:
    from app.infrastructure.models.channel import Channel


class TelethonNotReadyError(RuntimeError):
    """Сессия Telethon не настроена или не авторизована."""


class TelethonPublishError(RuntimeError):
    """Ошибка публикации через MTProto."""


class TelegramUserPublisher:
    """Публикует пост от имени userbot-аккаунта (длинные подписи к медиа)."""

    @staticmethod
    def is_configured() -> bool:
        """Проверяет наличие credentials Telethon в окружении."""
        settings = get_settings()
        return bool(settings.telegram_api_id and settings.telegram_api_hash)

    async def publish(
        self,
        channel: Channel,
        text: str,
        image_bytes: bytes | None,
    ) -> str:
        """Отправляет фото/текст в канал через MTProto.

        Args:
            channel: канал (``platform_id`` = chat_id или @username).
            text: HTML-текст поста.
            image_bytes: обложка.

        Returns:
            str: message_id.

        Raises:
            TelethonNotReadyError: нет сессии или не авторизован.
            TelethonSessionBusyError: сессия занята другой задачей.
            TelethonPublishError: ошибка API.
        """
        if not self.is_configured():
            msg = "TELEGRAM_API_ID / TELEGRAM_API_HASH not configured"
            raise TelethonNotReadyError(msg)

        caption = to_telethon_html(text)[:TELEGRAM_USER_CAPTION_MAX]
        try:
            with telethon_session_lock():
                return await self._publish_locked(channel, caption, image_bytes)
        except TelethonSessionBusyError:
            raise
        except TelethonNotReadyError:
            raise
        except Exception as exc:
            if isinstance(exc, (TelethonPublishError, TelethonNotReadyError)):
                raise
            msg = f"Telethon publish failed: {exc}"
            raise TelethonPublishError(msg) from exc

    async def _publish_locked(
        self,
        channel: Channel,
        text: str,
        image_bytes: bytes | None,
    ) -> str:
        settings = get_settings()
        target: str | int = (
            int(channel.platform_id.strip())
            if _is_numeric_chat_id(channel.platform_id)
            else _normalize_telegram_channel(channel.platform_id)
        )

        client = TelegramClient(
            SESSION_PATH,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            msg = (
                "Telethon session not authorized — run "
                "scripts/telethon_login.py (аккаунт должен быть админом канала)"
            )
            raise TelethonNotReadyError(msg)

        try:
            entity = await client.get_entity(target)
            if image_bytes:
                image_stream = io.BytesIO(image_bytes)
                # Telethon определяет тип медиа по имени файла: без него
                # картинка уходит как документ ("unnamed"), а не как фото.
                image_stream.name = "post.jpg"
                message = await client.send_file(
                    entity,
                    file=image_stream,
                    caption=text,
                    parse_mode="html",
                    force_document=False,
                )
            else:
                message = await client.send_message(
                    entity,
                    text,
                    parse_mode="html",
                )
            logger.info(
                "Telegram userbot published",
                channel_id=channel.id,
                message_id=message.id,
                text_length=len(text),
                with_media=bool(image_bytes),
            )
            return str(message.id)
        except FloodWaitError as exc:
            msg = f"Telethon flood wait: {exc.seconds}s"
            raise TelethonPublishError(msg) from exc
        except (ChatWriteForbiddenError, UserNotParticipantError) as exc:
            msg = (
                "Telethon account cannot post to channel — "
                "добавьте аккаунт сессии админом канала с правом публикации"
            )
            raise TelethonPublishError(msg) from exc
        except RPCError as exc:
            msg = f"Telethon RPC error: {exc}"
            raise TelethonPublishError(msg) from exc
        finally:
            await client.disconnect()
