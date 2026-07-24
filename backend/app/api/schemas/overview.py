"""Схемы API обзорной панели (главная страница)."""

from datetime import datetime

from pydantic import BaseModel, Field


class OverviewKpis(BaseModel):
    """Ключевые показатели для KPI-ряда."""

    subscribers_total: int
    subscribers_delta_today: int | None
    publications_today_success: int
    publications_today_failed: int
    total_views: int | None
    queue_pending: int
    approved_queue: int
    active_jobs: int
    materials_unprocessed: int


class AttentionItem(BaseModel):
    """Элемент блока «Требует внимания»."""

    key: str
    label: str
    count: int
    route: str
    severity: str = Field(pattern="^(info|warning|danger)$")


class TopChannelItem(BaseModel):
    """Краткая карточка канала для топа."""

    channel_id: int
    name: str
    platform: str
    subscribers: int | None
    subscribers_delta: int | None
    engagement_rate: float | None
    total_views: int | None = None


class RecentPublication(BaseModel):
    """Последняя попытка публикации."""

    id: int
    channel_name: str | None
    status: str
    attempted_at: datetime
    preview: str | None = None


class OverviewTrendPoint(BaseModel):
    """Точка агрегированного графика подписчиков."""

    captured_at: str
    label: str
    value: int


class PlatformStatus(BaseModel):
    """Статус автоматизации платформы."""

    schedule_fetch_enabled: bool
    schedule_publish_enabled: bool
    schedule_ai_enabled: bool


class OverviewResponse(BaseModel):
    """Полный ответ обзорной панели."""

    kpis: OverviewKpis
    attention: list[AttentionItem]
    top_channels: list[TopChannelItem]
    recent_publications: list[RecentPublication]
    trend: list[OverviewTrendPoint]
    platform_status: PlatformStatus
