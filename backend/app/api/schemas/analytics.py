"""Схемы API аналитики каналов."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.api.schemas.channel import ChannelResponse
from app.api.schemas.common import OrmSchema


class GrowthPoint(BaseModel):
    """Точка графика подписчиков в обзоре канала (legacy overview)."""

    captured_at: str
    subscribers: int | None


class ChartGrowthPoint(BaseModel):
    """Точка графика с агрегированным значением метрики."""

    captured_at: str
    value: int | None


class GrowthHistoryResponse(BaseModel):
    """История графика за период с сравнением к прошлому."""

    period: str
    metric: str
    granularity: str
    points: list[ChartGrowthPoint]
    period_total: int | None
    period_delta: int | None
    period_delta_percent: float | None
    previous_period_label: str | None
    subscribers_unsubscribed: int | None = None


class MaxMemberResponse(OrmSchema):
    """Участник MAX-канала для API."""

    user_id: int
    first_name: str | None
    last_name: str | None
    name: str | None
    username: str | None
    avatar_url: str | None
    is_bot: bool
    is_admin: bool
    is_owner: bool
    permissions: str | None
    join_at: datetime | None
    last_access_at: datetime | None
    last_activity_at: datetime | None
    is_present: bool
    left_at: datetime | None


class MemberJoinsPoint(BaseModel):
    """Вступления за один день."""

    day: str
    count: int


class TelegramBroadcastStatsResponse(OrmSchema):
    """Нативная статистика Telegram-канала (stats.getBroadcastStats)."""

    followers: int | None
    followers_prev: int | None
    views_per_post: float | None
    views_per_post_prev: float | None
    shares_per_post: float | None
    shares_per_post_prev: float | None
    reactions_per_post: float | None
    reactions_per_post_prev: float | None
    enabled_notifications_pct: float | None
    period_min: datetime | None
    period_max: datetime | None
    collected_at: datetime


class MaxMemberAnalyticsResponse(BaseModel):
    """Аналитика подписчиков MAX-канала."""

    members_present: int
    joined_24h: int
    joined_7d: int
    joined_30d: int
    left_7d: int
    left_30d: int
    active_access_7d: int
    active_activity_24h: int
    admins_count: int
    joins_by_day: list[MemberJoinsPoint]
    recent_members: list[MaxMemberResponse]


class AnalyticsSummaryResponse(BaseModel):
    """Общая сводка dashboard."""

    channels_total: int
    subscribers_total: int
    publications_total: int
    total_views: int | None
    avg_views: float | None
    ad_integrations_total: int
    ad_revenue_total: float


class ChannelAnalyticsResponse(BaseModel):
    """Сводка по одному каналу."""

    channel: ChannelResponse
    subscribers: int | None
    subscribers_delta: int | None
    subscribers_today: int | None = None
    subscribers_week: int | None = None
    subscribers_unsubscribed_total: int | None
    posts_count: int | None
    platform_posts_count: int | None
    total_views: int | None
    avg_views: float | None
    views_24h: int | None = None
    views_48h: int | None = None
    views_72h: int | None = None
    avg_reach: float | None
    engagement_rate: float | None
    publications_total: int
    ad_integrations_count: int
    ad_revenue_total: float
    growth_points: list[GrowthPoint]
    last_collected_at: datetime | None


class PostMetricResponse(OrmSchema):
    """Метрики поста."""

    id: int
    channel_id: int
    processed_post_id: int | None
    publish_log_id: int | None
    platform_post_id: str
    post_url: str | None
    views: int | None
    forwards: int | None
    reactions: int | None
    comments: int | None
    reach: int | None
    reach_subscribers: int | None = None
    published_at: datetime | None
    collected_at: datetime
    rewritten_text: str | None = None
    post_text: str | None = None


class AdIntegrationCreate(BaseModel):
    """Создание рекламной интеграции."""

    channel_id: int
    processed_post_id: int | None = None
    platform_post_id: str | None = None
    post_url: str | None = None
    advertiser: str = Field(..., max_length=255)
    price: Decimal | None = None
    currency: str = Field("RUB", max_length=8)
    placed_at: datetime
    status: str = Field("published", pattern="^(planned|published|completed)$")
    note: str | None = None


class AdIntegrationUpdate(BaseModel):
    """Обновление рекламной интеграции."""

    channel_id: int | None = None
    processed_post_id: int | None = None
    platform_post_id: str | None = None
    post_url: str | None = None
    advertiser: str | None = Field(None, max_length=255)
    price: Decimal | None = None
    currency: str | None = Field(None, max_length=8)
    placed_at: datetime | None = None
    status: str | None = Field(None, pattern="^(planned|published|completed)$")
    note: str | None = None


class RefreshJobResponse(BaseModel):
    """Ответ на запуск сбора статистики (с id задачи для отслеживания)."""

    message: str
    job_id: str


class ChannelRefreshProgress(BaseModel):
    """Прогресс по одному каналу в рамках сбора статистики."""

    id: int
    name: str
    platform: str
    status: str
    subscribers: int | None = None
    posts: int | None = None
    total_views: int | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class RefreshProgressResponse(BaseModel):
    """Состояние задачи сбора статистики для всплывающего окна прогресса."""

    job_id: str
    status: str
    total: int
    completed: int
    started_at: str | None = None
    finished_at: str | None = None
    channels: list[ChannelRefreshProgress]


class AdIntegrationResponse(OrmSchema):
    """Ответ рекламной интеграции."""

    id: int
    channel_id: int
    processed_post_id: int | None
    platform_post_id: str | None
    post_url: str | None
    advertiser: str
    price: Decimal | None
    currency: str
    placed_at: datetime
    status: str
    note: str | None
    created_at: datetime
    channel: ChannelResponse | None = None
