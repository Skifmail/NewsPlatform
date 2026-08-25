"""Схемы постов."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.api.schemas.channel import ChannelResponse
from app.api.schemas.common import OrmSchema
from app.infrastructure.media_store import public_media_url


class RawPostPreview(OrmSchema):
    """Превью сырого поста."""

    id: int
    title: str | None
    content: str
    url: str | None
    image_url: str | None
    topic: str
    published_at: datetime | None


class ProcessedPostResponse(OrmSchema):
    """Детальный обработанный пост."""

    id: int
    raw_post_id: int | None
    channel_id: int
    rewritten_text: str
    content_mode: str
    article_title: str | None = None
    article_body: str | None = None
    telegraph_url: str | None = None
    research_sources: str | None = None
    generated_image_url: str | None
    generated_video_url: str | None
    image_source: str | None
    ai_model: str | None
    status: str
    published_at: datetime | None
    rejection_reason: str | None
    last_publish_status: str | None = None
    last_publish_error: str | None = None
    last_publish_attempt_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    raw_post: RawPostPreview | None = None
    channel: ChannelResponse | None = None

    @model_validator(mode="after")
    def _expose_public_media_urls(self) -> "ProcessedPostResponse":
        self.generated_image_url = public_media_url(self.generated_image_url)
        self.generated_video_url = public_media_url(self.generated_video_url)
        return self


class PublishHistoryResponse(BaseModel):
    """Запись истории попытки публикации."""

    id: int
    processed_post_id: int | None
    channel: ChannelResponse | None = None
    status: str
    error_message: str | None = None
    attempted_at: datetime
    rewritten_text: str | None = None


class ApproveRequest(BaseModel):
    """Запрос одобрения."""

    rewritten_text: str | None = None
    generated_image_url: str | None = None
    generated_video_url: str | None = None
    publish_immediately: bool = False


class RejectRequest(BaseModel):
    """Запрос отклонения."""

    reason: str = Field(..., min_length=1)


class UpdatePostRequest(BaseModel):
    """Обновление текста поста."""

    rewritten_text: str | None = None
    generated_image_url: str | None = None
    generated_video_url: str | None = None


class ApprovedSummaryResponse(BaseModel):
    """Сводка по одобренным постам."""

    total: int


class QueueBulkFilters(BaseModel):
    """Фильтры для массовой очистки очереди модерации."""

    channel_id: int | None = None
    topic: str | None = None
    older_than_days: int | None = Field(default=None, ge=1, le=365)


class QueueBulkRequest(BaseModel):
    """Массовое отклонение или удаление постов из очереди pending."""

    action: Literal["reject", "delete"]
    post_ids: list[int] | None = Field(default=None, max_length=500)
    filters: QueueBulkFilters | None = None
    reason: str | None = Field(default=None, min_length=1)
    dry_run: bool = False

    @model_validator(mode="after")
    def validate_selection(self) -> "QueueBulkRequest":
        has_ids = bool(self.post_ids)
        has_filters = bool(
            self.filters
            and (
                self.filters.channel_id is not None
                or self.filters.topic is not None
                or self.filters.older_than_days is not None
            )
        )
        if not has_ids and not has_filters:
            msg = "Укажите post_ids или хотя бы один фильтр"
            raise ValueError(msg)
        if self.action == "reject" and not self.dry_run and not self.reason:
            msg = "Для отклонения укажите reason"
            raise ValueError(msg)
        return self


class ManualPublishRequest(BaseModel):
    """Запрос ручной публикации поста в канал."""

    channel_id: int = Field(..., ge=1)
    text: str = Field(..., min_length=1)
    button_1: str = Field(..., min_length=1, max_length=64)
    button_2: str = Field(..., min_length=1, max_length=64)
    image_url: str | None = None
    video_url: str | None = None
    publish_immediately: bool = True


class MediaUploadResponse(BaseModel):
    """Ответ после загрузки файла в медиахранилище."""

    url: str
    public_url: str
    kind: Literal["image", "video"]
    filename: str
    size: int
