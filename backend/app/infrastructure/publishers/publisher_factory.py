"""Фабрика публикаторов."""

from app.domain.enums import Platform
from app.infrastructure.models.channel import Channel
from app.infrastructure.publishers.base import BasePublisher
from app.infrastructure.publishers.max_publisher import MaxPublisher
from app.infrastructure.publishers.telegram_publisher import TelegramPublisher
from app.infrastructure.publishers.vk_publisher import VkPublisher


def get_publisher(channel: Channel) -> BasePublisher:
    """Возвращает публикатор для платформы канала.

    Args:
        channel: канал.

    Returns:
        BasePublisher: реализация.

    Raises:
        ValueError: неизвестная платформа.
    """
    if channel.platform in (Platform.TELEGRAM.value,):
        return TelegramPublisher()
    if channel.platform == Platform.MAX.value:
        return MaxPublisher()
    if channel.platform == Platform.VK.value:
        return VkPublisher()
    msg = f"Unknown platform: {channel.platform}"
    raise ValueError(msg)
