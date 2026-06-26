"""Общие Pydantic-схемы."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class OrmSchema(BaseModel):
    """Базовая схема с ORM mode."""

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    """Ответ с сообщением."""

    message: str


class IdListResponse(BaseModel):
    """Список созданных ID."""

    ids: list[int]


class BulkActionResponse(BaseModel):
    """Результат массовой операции."""

    message: str
    affected: int
    skipped: int = 0
    dry_run: bool = False
