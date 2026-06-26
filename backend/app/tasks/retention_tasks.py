"""Celery-задачи очистки устаревших данных."""

from loguru import logger

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.services.retention_service import RetentionService
from app.tasks.async_runner import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(name="app.tasks.retention_tasks.cleanup_old_records")
def cleanup_old_records() -> dict[str, int]:
    """Удаляет записи старше RETENTION_DAYS дней.

    Returns:
        dict[str, int]: счётчики удалённых строк по таблицам.
    """

    async def _run() -> dict[str, int]:
        from app.services.platform_settings_service import PlatformSettingsService

        settings = get_settings()
        async with async_session_factory() as session:
            ps = await PlatformSettingsService(session).load()
            if not ps.schedule_retention_enabled:
                logger.info("Retention skipped: schedule_retention_enabled=false")
                return {
                    "publish_logs": 0,
                    "background_jobs": 0,
                    "raw_posts": 0,
                }
            stats = await RetentionService(
                session,
                retention_days=settings.retention_days,
            ).cleanup_expired()
        return {
            "publish_logs": stats.publish_logs,
            "background_jobs": stats.background_jobs,
            "raw_posts": stats.raw_posts,
        }

    result = run_async(_run())
    logger.info("Scheduled retention finished", **result)
    return result
