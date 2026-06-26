"""Схемы фоновых задач."""

from datetime import datetime

from pydantic import BaseModel

from app.api.schemas.common import OrmSchema


class BackgroundJobResponse(OrmSchema):
    """Задача для панели."""

    id: int
    celery_task_id: str
    job_type: str
    status: str
    label: str
    source_id: int | None
    raw_post_id: int | None
    parent_celery_task_id: str | None
    result_summary: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class BackgroundJobActivityResponse(BackgroundJobResponse):
    """Задача с полями для toast-уведомления."""

    progress: int
    phase: str
    detail: str


class JobsSummaryResponse(BaseModel):
    """Сводка по задачам."""

    queued: int
    running: int
    success: int
    failed: int
    active_total: int


class FetchQueuedResponse(BaseModel):
    """Ответ на запуск парсинга."""

    message: str
    celery_task_id: str
    job_id: int


class ProcessQueuedResponse(BaseModel):
    """Ответ на повторный запуск AI-обработки."""

    message: str
    celery_task_id: str
    job_id: int
