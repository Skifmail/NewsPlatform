"""Фабрика сборщиков статистики по платформе."""

from app.domain.enums import Platform
from app.infrastructure.models.channel import Channel
from app.infrastructure.stats.base import BaseStatsCollector
from app.infrastructure.stats.max_stats import MaxStatsCollector
from app.infrastructure.stats.telegram_stats import TelegramStatsCollector
from app.infrastructure.stats.vk_stats import VkStatsCollector


def get_stats_collector(channel: Channel) -> BaseStatsCollector:
    """Возвращает сборщик для платформы канала.

    Args:
        channel: канал публикации.

    Returns:
        BaseStatsCollector: реализация для telegram/vk/max.

    Raises:
        ValueError: неизвестная платформа.
    """
    platform = channel.platform.lower()
    if platform == Platform.TELEGRAM.value:
        return TelegramStatsCollector()
    if platform == Platform.VK.value:
        return VkStatsCollector()
    if platform == Platform.MAX.value:
        return MaxStatsCollector()
    msg = f"Unsupported platform for analytics: {channel.platform}"
    raise ValueError(msg)
