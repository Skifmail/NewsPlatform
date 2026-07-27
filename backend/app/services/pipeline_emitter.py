"""Контекст и хелперы для детального прогресса пайплайна."""

from __future__ import annotations

import contextvars
from typing import Any

from app.services.pipeline_progress import (
    PipelineProgressWriter,
    resume_or_create_writer,
)

_writer_ctx: contextvars.ContextVar[PipelineProgressWriter | None] = contextvars.ContextVar(
    "pipeline_writer",
    default=None,
)


def bind_pipeline(
    celery_task_id: str,
    *,
    job_type: str,
    label: str,
) -> PipelineProgressWriter:
    """Привязывает writer к текущей Celery-задаче."""
    writer = resume_or_create_writer(
        celery_task_id,
        job_type=job_type,
        label=label,
    )
    _writer_ctx.set(writer)
    return writer


def get_writer() -> PipelineProgressWriter | None:
    """Возвращает writer текущей задачи или None."""
    return _writer_ctx.get()


def ensure_writer(
    celery_task_id: str | None = None,
    *,
    job_type: str = "unknown",
    label: str = "Задача",
) -> PipelineProgressWriter | None:
    """Возвращает активный writer или восстанавливает по celery_task_id."""
    writer = get_writer()
    if writer and (not celery_task_id or writer.celery_task_id == celery_task_id):
        return writer
    if not celery_task_id:
        return None
    return bind_pipeline(celery_task_id, job_type=job_type, label=label)


def unbind_pipeline() -> None:
    """Сбрасывает writer после завершения задачи."""
    _writer_ctx.set(None)


def finish_pipeline(*, status: str = "done") -> None:
    """Завершает пайплайн, если writer активен."""
    writer = get_writer()
    if writer:
        writer.finish(status=status)


def sync_overview(
    detail: str,
    progress: int,
    *,
    celery_task_id: str | None = None,
) -> None:
    """Синхронизирует общий прогресс с report_job_stage.

    Если ContextVar потерян (отдельный loop / fork), восстанавливает writer
    по ``celery_task_id`` из Redis.
    """
    writer = ensure_writer(celery_task_id)
    if writer:
        writer.set_overview(detail, progress)


def emit_internal(
    *,
    label: str,
    detail: str | None = None,
    progress: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Добавляет внутренний этап платформы."""
    writer = get_writer()
    if writer:
        writer.emit_internal(
            label=label,
            detail=detail,
            progress=progress,
            metadata=metadata,
        )


def begin_step(**kwargs: Any) -> str | None:
    """Начинает шаг обмена; возвращает event_id или None."""
    writer = get_writer()
    if not writer:
        return None
    return writer.begin_step(**kwargs)


def complete_step(event_id: str | None, **kwargs: Any) -> None:
    """Завершает шаг, если writer и event_id заданы."""
    if not event_id:
        return
    writer = get_writer()
    if writer:
        writer.complete_step(event_id, **kwargs)


def fail_step(event_id: str | None, error: str) -> None:
    """Помечает шаг ошибкой."""
    if not event_id:
        return
    writer = get_writer()
    if writer:
        writer.fail_step(event_id, error)


def skip_step(**kwargs: Any) -> None:
    """Добавляет пропущенный шаг."""
    writer = get_writer()
    if writer:
        writer.skip_step(**kwargs)
