"""Роутер мониторинга фоновых задач."""

from fastapi import APIRouter, HTTPException

from app.api.deps import AuthDep, DbSession
from app.api.deps_platform import require_manual_ai
from app.api.schemas.job import (
    BackgroundJobActivityResponse,
    BackgroundJobResponse,
    JobsSummaryResponse,
    PipelineProgressResponse,
    ProcessQueuedResponse,
)
from app.services.activity_notifier import detail_for_job, phase_for_status, progress_for_job
from app.repositories.raw_post_repository import RawPostRepository
from app.services.job_cancel import cancel_job_by_celery_id
from app.services.job_tracker import JobTracker
from app.tasks.ai_tasks import process_post_task
from app.domain.enums import JobStatus
from app.repositories.background_job_repository import BackgroundJobRepository
from app.services.job_execution import reconcile_jobs_with_celery
from app.services.pipeline_progress import read_pipeline_progress_async

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("", response_model=list[BackgroundJobResponse])
async def list_jobs(
    session: DbSession,
    _: AuthDep,
    limit: int = 80,
) -> list[BackgroundJobResponse]:
    """Последние фоновые задачи (парсинг, AI, публикация).

    Args:
        limit: максимум записей.

    Returns:
        list[BackgroundJobResponse]: история задач.
    """
    await reconcile_jobs_with_celery(session)
    jobs = await BackgroundJobRepository(session).list_recent(limit=min(limit, 200))
    return jobs


@router.get("/active", response_model=list[BackgroundJobActivityResponse])
async def list_active_jobs(
    session: DbSession, _: AuthDep
) -> list[BackgroundJobActivityResponse]:
    """Активные задачи (queued/running) для live-уведомлений.

    Returns:
        list[BackgroundJobActivityResponse]: задачи с прогрессом.
    """
    await reconcile_jobs_with_celery(session)
    jobs = await BackgroundJobRepository(session).list_non_terminal(limit=30)
    return [
        BackgroundJobActivityResponse(
            id=job.id,
            celery_task_id=job.celery_task_id,
            job_type=job.job_type,
            status=job.status,
            label=job.label,
            source_id=job.source_id,
            raw_post_id=job.raw_post_id,
            parent_celery_task_id=job.parent_celery_task_id,
            result_summary=job.result_summary,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            progress=progress_for_job(job),
            phase=phase_for_status(job.status),
            detail=detail_for_job(job),
        )
        for job in jobs
    ]


@router.get("/pipeline/{celery_task_id}", response_model=PipelineProgressResponse)
async def get_pipeline_progress(
    celery_task_id: str,
    _: AuthDep,
) -> PipelineProgressResponse:
    """Детальный пошаговый прогресс пайплайна (Redis, TTL ~10 мин).

    Args:
        celery_task_id: ID задачи Celery.

    Returns:
        PipelineProgressResponse: события и текущий этап.

    Raises:
        HTTPException: если прогресс не найден или истёк TTL.
    """
    data = await read_pipeline_progress_async(celery_task_id)
    if not data:
        raise HTTPException(status_code=404, detail="Pipeline progress not found")
    return PipelineProgressResponse(**data)


@router.get("/summary", response_model=JobsSummaryResponse)
async def jobs_summary(session: DbSession, _: AuthDep) -> JobsSummaryResponse:
    """Сводка по статусам задач.

    Returns:
        JobsSummaryResponse: счётчики для дашборда.
    """
    await reconcile_jobs_with_celery(session)
    repo = BackgroundJobRepository(session)
    counts = await repo.count_by_status()
    queued = counts.get(JobStatus.QUEUED.value, 0)
    running = counts.get(JobStatus.RUNNING.value, 0)
    success = counts.get(JobStatus.SUCCESS.value, 0)
    failed = counts.get(JobStatus.FAILED.value, 0)
    return JobsSummaryResponse(
        queued=queued,
        running=running,
        success=success,
        failed=failed,
        active_total=queued + running,
    )


@router.post(
    "/{celery_task_id}/cancel",
    response_model=BackgroundJobActivityResponse,
)
async def cancel_job(
    celery_task_id: str,
    session: DbSession,
    _: AuthDep,
) -> BackgroundJobActivityResponse:
    """Отменяет Celery-задачу (revoke + terminate) и дочерние задачи.

    Args:
        celery_task_id: ID задачи Celery.

    Returns:
        BackgroundJobActivityResponse: обновлённый статус для UI.

    Raises:
        HTTPException: не найдена или уже завершена.
    """
    try:
        job = await cancel_job_by_celery_id(session, celery_task_id)
        await session.commit()
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    return BackgroundJobActivityResponse(
        id=job.id,
        celery_task_id=job.celery_task_id,
        job_type=job.job_type,
        status=job.status,
        label=job.label,
        source_id=job.source_id,
        raw_post_id=job.raw_post_id,
        parent_celery_task_id=job.parent_celery_task_id,
        result_summary=job.result_summary,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress=progress_for_job(job),
        phase=phase_for_status(job.status),
        detail=detail_for_job(job),
    )


@router.post(
    "/retry-process/{raw_post_id}",
    response_model=ProcessQueuedResponse,
)
async def retry_process(
    raw_post_id: int,
    session: DbSession,
    _: AuthDep,
) -> ProcessQueuedResponse:
    """Повторно ставит AI-обработку сырого поста в очередь Celery.

    Args:
        raw_post_id: ID raw_post.

    Returns:
        ProcessQueuedResponse: ID задачи в Celery и в панели.

    Raises:
        HTTPException: если пост не найден или уже обработан.
    """
    raw = await RawPostRepository(session).get_by_id(raw_post_id)
    if not raw:
        raise HTTPException(status_code=404, detail="Raw post not found")
    if raw.is_processed:
        raise HTTPException(
            status_code=400,
            detail="Пост уже обработан; повтор недоступен",
        )
    await require_manual_ai(session)
    result = process_post_task.delay(raw_post_id)
    job = await JobTracker(session).enqueue_process(result.id, raw_post_id)
    await session.commit()
    return ProcessQueuedResponse(
        message="AI-обработка поставлена в очередь",
        celery_task_id=result.id,
        job_id=job.id,
    )
