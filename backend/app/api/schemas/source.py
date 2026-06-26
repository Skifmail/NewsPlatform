"""Схемы источников."""

from datetime import datetime

from pydantic import BaseModel, Field

from app.api.schemas.common import OrmSchema
from app.domain.topics import TOPIC_PATTERN


class SourceCreate(BaseModel):
    """Создание источника."""

    name: str = Field(..., max_length=255)
    type: str = Field(..., pattern="^(rss|telegram|web)$")
    url: str
    topic: str = Field(..., pattern=TOPIC_PATTERN)
    is_active: bool = True
    fetch_interval_minutes: int = 30
    parser_config: str | None = None


class SourceUpdate(BaseModel):
    """Обновление источника."""

    name: str | None = None
    type: str | None = Field(None, pattern="^(rss|telegram|web)$")
    url: str | None = None
    topic: str | None = Field(None, pattern=TOPIC_PATTERN)
    is_active: bool | None = None
    fetch_interval_minutes: int | None = None
    parser_config: str | None = None


class SourceResponse(OrmSchema):
    """Ответ источника."""

    id: int
    name: str
    type: str
    url: str
    topic: str
    is_active: bool
    fetch_interval_minutes: int
    parser_config: str | None
    last_fetched_at: datetime | None
    created_at: datetime
