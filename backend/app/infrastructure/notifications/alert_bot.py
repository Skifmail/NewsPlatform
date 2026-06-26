"""Уведомления владельцу через Telegram alert-бот."""

from aiogram import Bot
from loguru import logger

from app.core.config import get_settings


async def send_alert(message: str) -> None:
    """Отправляет уведомление владельцу.

    Args:
        message: текст уведомления.
    """
    settings = get_settings()
    if not settings.alert_bot_token or not settings.alert_chat_id:
        logger.debug("Alert bot not configured, skipping")
        return

    bot = Bot(token=settings.alert_bot_token)
    try:
        await bot.send_message(
            chat_id=settings.alert_chat_id,
            text=message,
        )
    except Exception as exc:
        logger.error("Alert send failed", error=str(exc))
    finally:
        await bot.session.close()
