"""Схемы сырых постов."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.api.schemas.common import OrmSchema


class RawPostResponse(OrmSchema):
    """Сырой пост для панели материалов."""

    id: int
    source_id: int
    source_name: str
    source_url: str
    external_id: str | None
    title: str | None
    content_preview: str
    url: str | None
    topic: str
    is_processed: bool
    fetched_at: datetime
    published_at: datetime | None


class RawPostSourceStats(BaseModel):
    """Счётчики по источнику."""

    source_id: int
    source_name: str
    topic: str
    total: int
    unprocessed: int


class RawPostsSummaryResponse(BaseModel):
    """Сводка сырых постов по источникам."""

    total: int
    unprocessed: int
    sources: list[RawPostSourceStats]


class ProcessRawPostRequest(BaseModel):
    """Пакетная постановка на AI."""

    raw_post_ids: list[int] = Field(..., min_length=1, max_length=50)


class ProcessRawPostQueuedItem(BaseModel):
    """Один поставленный в очередь пост."""

    raw_post_id: int
    job_id: int
    celery_task_id: str


class ProcessRawPostsBatchResponse(BaseModel):
    """Ответ на пакетную AI-обработку."""

    message: str
    queued: list[ProcessRawPostQueuedItem]
    skipped: list[int] = Field(default_factory=list)


class RawPostBulkFilters(BaseModel):
    """Фильтры для массового удаления материалов."""

    source_id: int | None = None
    topic: str | None = None
    is_processed: bool | None = None
    older_than_days: int | None = Field(default=None, ge=1, le=365)


class RawPostBulkDeleteRequest(BaseModel):
    """Массовое удаление сырых постов."""

    raw_post_ids: list[int] | None = Field(default=None, max_length=500)
    filters: RawPostBulkFilters | None = None
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_selection(self) -> "RawPostBulkDeleteRequest":
        has_ids = bool(self.raw_post_ids)
        has_filters = bool(
            self.filters
            and (
                self.filters.source_id is not None
                or self.filters.topic is not None
                or self.filters.is_processed is not None
                or self.filters.older_than_days is not None
            )
        )
        if not has_ids and not has_filters:
            msg = "Укажите raw_post_ids или хотя бы один фильтр"
            raise ValueError(msg)
        return self
