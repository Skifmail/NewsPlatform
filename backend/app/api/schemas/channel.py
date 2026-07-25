"""Схемы каналов."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.api.schemas.common import OrmSchema
from app.domain.article_schedule import format_publish_times, parse_publish_times
from app.domain.topics import TOPIC_PATTERN


def _normalize_publish_times_required(value: str) -> str:
    """Нормализует строку времён «HH:MM,HH:MM» (МСК); пусто → ошибка."""
    normalized = format_publish_times(parse_publish_times(value))
    if not normalized:
        msg = "publish_times must contain at least one HH:MM entry (МСК)"
        raise ValueError(msg)
    return normalized


def _normalize_publish_times_optional(value: str | None) -> str | None:
    """Нормализация для Update: None → не менять, иначе как в required."""
    if value is None:
        return None
    return _normalize_publish_times_required(value)


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
    post_footer: str | None = None
    content_mode: str = Field("news", pattern="^(news|article)$")
    is_active: bool = True
    publish_times: str = Field(..., max_length=255)

    _norm_times = field_validator("publish_times")(
        staticmethod(_normalize_publish_times_required)
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
    post_footer: str | None = None
    content_mode: str | None = Field(None, pattern="^(news|article)$")
    is_active: bool | None = None
    publish_times: str | None = Field(None, max_length=255)

    _norm_times = field_validator("publish_times")(
        staticmethod(_normalize_publish_times_optional)
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
    post_footer: str | None
    content_mode: str
    is_active: bool
    publish_times: str
    created_at: datetime
