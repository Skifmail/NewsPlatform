"""Сбор статистики каналов с соцплатформ."""

from app.infrastructure.stats.base import (
    BaseStatsCollector,
    ChannelStatsDTO,
    PostMetricDTO,
)
from app.infrastructure.stats.factory import get_stats_collector

__all__ = [
    "BaseStatsCollector",
    "ChannelStatsDTO",
    "PostMetricDTO",
    "get_stats_collector",
]
