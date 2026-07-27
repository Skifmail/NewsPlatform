"""Отмена фоновых Celery-задач пользователем."""

from __future__ import annotations

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import JobStatus
from app.infrastructure.models.background_job import BackgroundJob
from app.repositories.background_job_repository import BackgroundJobRepository
from app.services.job_tracker import JobTracker
from app.tasks.celery_app import celery_app

_TERMINAL = {
    JobStatus.SUCCESS.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
}


def _revoke_celery(celery_task_id: str) -> None:
    """Revoke a Celery task (queued or running)."""
    celery_app.control.revoke(celery_task_id, terminate=True, signal="SIGTERM")


async def cancel_job_by_celery_id(
    session: AsyncSession,
    celery_task_id: str,
) -> BackgroundJob:
    """Отменяет задачу и дочерние Celery-задачи.

    Args:
        session: SQLAlchemy session.
        celery_task_id: ID корневой Celery-задачи.

    Returns:
        BackgroundJob: обновлённая корневая запись.

    Raises:
        LookupError: задача не найдена.
        ValueError: задача уже завершена.
    """
    repo = BackgroundJobRepository(session)
    tracker = JobTracker(session)
    job = await repo.get_by_celery_id(celery_task_id)
    if not job:
        raise LookupError("Job not found")
    if job.status in _TERMINAL:
        raise ValueError(f"Job already finished with status={job.status}")

    children = await repo.list_children(celery_task_id)
    targets = [job, *children]
    for target in targets:
        if target.status in _TERMINAL:
            continue
        try:
            _revoke_celery(target.celery_task_id)
        except Exception as exc:
            logger.warning(
                "Celery revoke failed",
                celery_task_id=target.celery_task_id,
                error=str(exc),
            )
        await tracker.mark_cancelled(
            target.celery_task_id,
            "Отменено пользователем",
        )

    await session.flush()
    refreshed = await repo.get_by_celery_id(celery_task_id)
    assert refreshed is not None
    logger.info(
        "Job cancelled by user",
        celery_task_id=celery_task_id,
        job_id=refreshed.id,
        children=len(children),
    )
    return refreshed
