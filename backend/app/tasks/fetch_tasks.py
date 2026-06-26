"""Celery-задачи парсинга."""

from loguru import logger

from app.domain.fetch_result import FetchResult
from app.infrastructure.database import async_session_factory
from app.services.fetch_service import FetchService
from app.services.job_execution import with_job_tracking
from app.services.job_tracker import JobTracker, _format_fetch_result
from app.services.platform_settings_service import PlatformSettingsService
from app.tasks.ai_tasks import process_post_task
from app.tasks.async_runner import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.tasks.fetch_tasks.fetch_source",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def fetch_source_task(self, source_id: int, manual: bool = False) -> list[int]:
    """Парсит один источник.

    Args:
        source_id: ID источника.
        manual: True — запуск из панели «Парсить».

    Returns:
        list[int]: ID новых raw_posts.
    """

    task_id = self.request.id

    async def _work() -> object:
        async with async_session_factory() as session:
            ps = await PlatformSettingsService(session).load()
            if manual and not ps.manual_fetch_enabled:
                logger.warning(
                    "Manual fetch skipped: disabled in settings",
                    source_id=source_id,
                )
                return FetchResult(created_ids=[])
            if not manual and not ps.schedule_fetch_enabled:
                logger.warning(
                    "Scheduled fetch skipped: disabled in settings",
                    source_id=source_id,
                )
                return FetchResult(created_ids=[])

            outcome = await FetchService(session).fetch_source(
                source_id,
                celery_task_id=task_id,
            )
            tracker = JobTracker(session)
            if ps.should_queue_ai_after_fetch(manual):
                for raw_id in outcome.created_ids:
                    child = process_post_task.delay(raw_id)
                    await tracker.enqueue_process(child.id, raw_id, task_id)
            elif outcome.created_ids:
                logger.info(
                    "AI after fetch disabled; raw posts saved only",
                    count=len(outcome.created_ids),
                    manual=manual,
                )
            await session.commit()
            return outcome

    async def _run() -> object:
        return await with_job_tracking(task_id, _format_fetch_result, _work)

    outcome = run_async(_run())
    if isinstance(outcome, FetchResult):
        return outcome.created_ids
    return outcome


@celery_app.task(name="app.tasks.fetch_tasks.fetch_all_sources")
def fetch_all_sources() -> int:
    """Парсит все активные источники (устаревший вызов; предпочтителен scheduler).

    Returns:
        int: число запущенных задач.
    """

    async def _run() -> int:
        from app.repositories.source_repository import SourceRepository

        async with async_session_factory() as session:
            ps = await PlatformSettingsService(session).load()
            if not ps.schedule_fetch_enabled:
                logger.info("fetch_all_sources skipped: schedule_fetch_enabled=false")
                return 0
            sources = await SourceRepository(session).list_active()
            count = 0
            for source in sources:
                fetch_source_task.delay(source.id, manual=False)
                count += 1
            await PlatformSettingsService(session).mark_fetch_run()
            await session.commit()
            logger.info("Scheduled fetch for sources", count=count)
            return count

    return run_async(_run())
