"""DTO и базовый класс сборщиков статистики."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

from app.infrastructure.models.channel import Channel


@dataclass(frozen=True)
class PostMetricDTO:
    """Метрики одного поста с платформы."""

    platform_post_id: str
    post_url: str | None = None
    text: str | None = None
    views: int | None = None
    forwards: int | None = None
    reactions: int | None = None
    comments: int | None = None
    reach: int | None = None
    reach_subscribers: int | None = None
    published_at: datetime | None = None


@dataclass(frozen=True)
class MemberDTO:
    """Участник канала со всей доступной от платформы информацией.

    Заполняется платформами, отдающими список участников (MAX). Для
    остальных остаётся пустым.
    """

    user_id: int
    first_name: str | None = None
    last_name: str | None = None
    name: str | None = None
    username: str | None = None
    avatar_url: str | None = None
    is_bot: bool = False
    is_admin: bool = False
    is_owner: bool = False
    permissions: list[str] | None = None
    join_at: datetime | None = None
    last_access_at: datetime | None = None
    last_activity_at: datetime | None = None


@dataclass(frozen=True)
class BroadcastStatsDTO:
    """Нативная статистика Telegram-канала (stats.getBroadcastStats).

    Доступна только для достаточно крупных каналов и при user-аккаунте-админе.
    Для мелких каналов остаётся None (сбор тихо пропускается).
    """

    followers: float | None = None
    followers_prev: float | None = None
    views_per_post: float | None = None
    views_per_post_prev: float | None = None
    shares_per_post: float | None = None
    shares_per_post_prev: float | None = None
    reactions_per_post: float | None = None
    reactions_per_post_prev: float | None = None
    enabled_notifications_pct: float | None = None
    period_min: datetime | None = None
    period_max: datetime | None = None


@dataclass(frozen=True)
class ChannelStatsDTO:
    """Агрегированная статистика канала с платформы."""

    subscribers: int | None = None
    posts_count: int | None = None
    total_views: int | None = None
    post_metrics: list[PostMetricDTO] = field(default_factory=list)
    members: list[MemberDTO] = field(default_factory=list)
    broadcast_stats: BroadcastStatsDTO | None = None


class BaseStatsCollector(ABC):
    """Интерфейс сборщика статистики для одной платформы."""

    @abstractmethod
    async def collect(
        self,
        channel: Channel,
        *,
        known_post_ids: list[str] | None = None,
    ) -> ChannelStatsDTO:
        """Собирает статистику канала и постов.

        Args:
            channel: канал публикации.
            known_post_ids: ID постов из publish_log для точечного сбора.

        Returns:
            ChannelStatsDTO: метрики канала и постов.
        """
