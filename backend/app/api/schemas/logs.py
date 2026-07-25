"""Схемы окна диагностики: логи ошибок и здоровье конвейера."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AppErrorLogResponse(BaseModel):
    """Одна запись лога ошибки."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    level: str
    service: str
    source: str
    message: str
    context: str | None = None


class ChannelPublishHealthResponse(BaseModel):
    """Последняя публикация канала."""

    channel_id: int
    name: str
    last_published_at: datetime | None = None
    hours_since: float | None = None


class PipelineHealthResponse(BaseModel):
    """Сводка здоровья конвейера публикаций."""

    status: str
    reason: str
    last_publish_at: datetime | None = None
    last_fetch_at: datetime | None = None
    failed_jobs_24h: int
    errors_1h: int
    errors_24h: int
    in_active_window: bool
    channels: list[ChannelPublishHealthResponse]
