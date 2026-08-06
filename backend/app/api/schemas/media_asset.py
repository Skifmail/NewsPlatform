"""Схемы медиатеки."""

from datetime import datetime

from pydantic import BaseModel, model_validator

from app.api.schemas.channel import ChannelResponse
from app.api.schemas.common import OrmSchema
from app.infrastructure.media_store import public_media_url


class MediaAssetResponse(OrmSchema):
    """Запись медиатеки для галереи."""

    id: int
    channel_id: int
    processed_post_id: int | None
    kind: str
    image_source: str | None
    storage_url: str | None
    title: str | None
    created_at: datetime
    channel: ChannelResponse | None = None
    is_downloadable: bool = False

    @model_validator(mode="after")
    def _expose_public_url(self) -> "MediaAssetResponse":
        raw = self.storage_url
        self.is_downloadable = bool(raw and raw.startswith("local://"))
        self.storage_url = public_media_url(raw)
        return self


class MediaAssetBackfillResponse(BaseModel):
    """Результат импорта существующих постов в медиатеку."""

    imported: int
