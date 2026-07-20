"""Схемы каналов."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.common import OrmSchema
from app.domain.article_schedule import format_publish_times, parse_publish_times
from app.domain.topics import TOPIC_PATTERN


def _normalize_publish_times(value: str | None) -> str | None:
    """Нормализует строку времён «HH:MM,HH:MM» (МСК); пустое → None."""
    if value is None:
        return None
    normalized = format_publish_times(parse_publish_times(value))
    return normalized or None


class ChannelCreate(BaseModel):
    """Создание канала."""

    name: str = Field(..., max_length=255)
    platform: str = Field(..., pattern="^(telegram|vk|max)$")
    platform_id: str = Field(..., max_length=255)
    topic: str = Field(..., pattern=TOPIC_PATTERN)
    style_prompt: str | None = None
    image_prompt_guidelines: str | None = None
    cross_promote_url: str | None = Field(None, max_length=512)
    cross_promote_label: str | None = Field(None, max_length=255)
    cross_promote_emoji_id: str | None = Field(None, max_length=32)
    content_mode: str = Field("news", pattern="^(news|article)$")
    is_active: bool = True
    publish_interval_minutes: int = Field(60, ge=1, le=1440)
    publish_window_start: str = Field("08:00", pattern=r"^\d{2}:\d{2}$")
    publish_window_end: str = Field("22:00", pattern=r"^\d{2}:\d{2}$")
    publish_times: str | None = Field(None, max_length=255)

    _norm_times = field_validator("publish_times")(
        staticmethod(_normalize_publish_times)
    )


class ChannelUpdate(BaseModel):
    """Обновление канала."""

    name: str | None = None
    platform: str | None = Field(None, pattern="^(telegram|vk|max)$")
    platform_id: str | None = None
    topic: str | None = Field(None, pattern=TOPIC_PATTERN)
    style_prompt: str | None = None
    image_prompt_guidelines: str | None = None
    cross_promote_url: str | None = Field(None, max_length=512)
    cross_promote_label: str | None = Field(None, max_length=255)
    cross_promote_emoji_id: str | None = Field(None, max_length=32)
    content_mode: str | None = Field(None, pattern="^(news|article)$")
    is_active: bool | None = None
    publish_interval_minutes: int | None = Field(None, ge=1, le=1440)
    publish_window_start: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    publish_window_end: str | None = Field(None, pattern=r"^\d{2}:\d{2}$")
    publish_times: str | None = Field(None, max_length=255)

    _norm_times = field_validator("publish_times")(
        staticmethod(_normalize_publish_times)
    )


class ChannelResponse(OrmSchema):
    """Ответ канала."""

    id: int
    name: str
    platform: str
    platform_id: str
    topic: str
    style_prompt: str | None
    image_prompt_guidelines: str | None
    cross_promote_url: str | None
    cross_promote_label: str | None
    cross_promote_emoji_id: str | None
    content_mode: str
    is_active: bool
    publish_interval_minutes: int
    publish_window_start: str
    publish_window_end: str
    publish_times: str | None
    created_at: datetime
