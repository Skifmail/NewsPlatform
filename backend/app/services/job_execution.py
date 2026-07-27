"""Выполнение Celery-задач с обновлением статуса в БД."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import TypeVar

from celery.result import AsyncResult
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import JobStatus, JobType
from app.infrastructure.database import async_session_factory
from app.infrastructure.models.background_job import BackgroundJob
from app.repositories.background_job_repository import BackgroundJobRepository
from app.services.activity_notifier import notify_job
from app.services.job_tracker import JobTracker, _format_fetch_result, _format_process_result
from app.services.pipeline_emitter import bind_pipeline, finish_pipeline, unbind_pipeline
from app.tasks.celery_app import celery_app

T = TypeVar("T")

# Задачи в PENDING дольше этого интервала считаем потерянными (restart worker / Redis).
_STALE_PENDING_AFTER = timedelta(minutes=15)


async def with_job_tracking(
    celery_task_id: str,
    success_summary: Callable[[T], str | None],
    fn: Callable[[], Awaitable[T]],
) -> T:
    """Выполняет корутину и синхронизирует статус background_jobs.

    Args:
        celery_task_id: ID задачи Celery.
        success_summary: формирует краткий итог по результату.
        fn: основная логика задачи.

    Returns:
        T: результат fn.

    Raises:
        Exception: пробрасывает исключение из fn после записи failed.
    """
    job: BackgroundJob | None = None
    async with async_session_factory() as session:
        await JobTracker(session).mark_running(celery_task_id)
        job = await BackgroundJobRepository(session).get_by_celery_id(celery_task_id)
        await session.commit()

    if job:
        bind_pipeline(
            celery_task_id,
            job_type=job.job_type,
            label=job.label or "Задача",
        )

    try:
        result = await fn()
        summary = success_summary(result)
        finish_pipeline(status="done")
        async with async_session_factory() as session:
            tracker = JobTracker(session)
            await tracker.mark_success(celery_task_id, summary)
            await session.commit()
            job = await BackgroundJobRepository(session).get_by_celery_id(
                celery_task_id
            )
            if job:
                await notify_job(job)
        return result
    except Exception as exc:
        finish_pipeline(status="error")
        async with async_session_factory() as session:
            tracker = JobTracker(session)
            await tracker.mark_failed(celery_task_id, str(exc))
            await session.commit()
            job = await BackgroundJobRepository(session).get_by_celery_id(
                celery_task_id
            )
            if job:
                await notify_job(job)
        raise
    finally:
        unbind_pipeline()


def _summary_for_job(job: BackgroundJob, result: object) -> str | None:
    """Формирует итог по типу задачи и результату Celery.

    Args:
        job: запись в background_jobs.
        result: retval из Celery.

    Returns:
        str | None: текст для панели.
    """
    if job.job_type == JobType.FETCH.value:
        return _format_fetch_result(result)
    if job.job_type == JobType.PROCESS.value:
        return _format_process_result(result)
    if job.job_type == JobType.PUBLISH.value:
        return "Публикация выполнена"
    if job.job_type == JobType.ARTICLE.value:
        if isinstance(result, int):
            return f"Статья создана: processed_post #{result}"
        return "Генерация статьи завершена"
    return None


async def reconcile_jobs_with_celery(session: AsyncSession) -> int:
    """Подтягивает статусы из Celery для зависших записей в БД.

    Args:
        session: сессия SQLAlchemy.

    Returns:
        int: число обновлённых записей.
    """
    repo = BackgroundJobRepository(session)
    tracker = JobTracker(session)
    jobs = await repo.list_non_terminal(limit=200)
    updated = 0
    for job in jobs:
        ar = AsyncResult(job.celery_task_id, app=celery_app)
        state = ar.state
        if state == "PENDING":
            created = job.created_at
            if created is not None:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=UTC)
                age = datetime.now(UTC) - created
                if age > _STALE_PENDING_AFTER:
                    await tracker.mark_failed(
                        job.celery_task_id,
                        "Задача потеряна: worker перезапущен или сброшена из очереди Celery",
                    )
                    updated += 1
            continue
        if state == "RECEIVED":
            continue
        if state in ("STARTED", "RETRY"):
            if job.status != JobStatus.RUNNING.value:
                await tracker.mark_running(job.celery_task_id)
                updated += 1
            continue
        if state == "SUCCESS":
            try:
                result = ar.result
            except Exception:
                result = None
            await tracker.mark_success(
                job.celery_task_id,
                _summary_for_job(job, result),
            )
            updated += 1
            continue
        if state == "FAILURE":
            try:
                error = str(ar.result)
            except Exception:
                error = "Ошибка выполнения задачи"
            await tracker.mark_failed(job.celery_task_id, error)
            updated += 1
    if updated:
        await session.commit()
        logger.debug("Reconciled background jobs from Celery", count=updated)
    return updated
