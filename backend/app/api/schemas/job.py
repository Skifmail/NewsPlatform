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


class PipelineEventResponse(BaseModel):
    """Один шаг детального прогресса."""

    id: str
    step_id: str
    label: str
    status: str
    progress: int
    direction: str
    from_node: str
    to_node: str
    provider: str | None = None
    model: str | None = None
    request_summary: str | None = None
    response_summary: str | None = None
    started_at: str
    finished_at: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    metadata: dict[str, object] | None = None


class PipelineProgressResponse(BaseModel):
    """Детальный прогресс пайплайна Celery-задачи."""

    celery_task_id: str
    job_type: str
    label: str
    status: str
    progress: int
    current_detail: str
    started_at: str
    finished_at: str | None = None
    events: list[PipelineEventResponse]
