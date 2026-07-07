"""Единый планировщик: парсинг, публикация, retention по настройкам БД."""

from datetime import UTC, datetime, timedelta

from loguru import logger

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.source_repository import SourceRepository
from app.services.article_scheduler_service import ArticleSchedulerService
from app.services.curated_publish_service import CuratedPublishService
from app.services.platform_settings_service import PlatformSettingsService
from app.services.retention_service import RetentionService
from app.tasks.async_runner import run_async
from app.tasks.analytics_tasks import collect_all_channels_stats
from app.tasks.celery_app import celery_app
from app.tasks.fetch_tasks import fetch_source_task
from app.tasks.publish_tasks import publish_post_task


@celery_app.task(name="app.tasks.scheduler_tasks.platform_scheduler_tick")
def platform_scheduler_tick() -> dict[str, int | bool]:
    """Раз в минуту проверяет настройки и запускает due-задачи.

    Returns:
        dict[str, int | bool]: счётчики и флаги срабатывания.
    """

    async def _run() -> dict[str, int | bool]:
        now = datetime.now(UTC)
        result: dict[str, int | bool | dict[str, int | None]] = {
            "publish_queued": 0,
            "fetch_sources_queued": 0,
            "retention_ran": False,
            "curated_queued": {},
            "article_queued": {},
            "analytics_queued": False,
        }
        async with async_session_factory() as session:
            settings_svc = PlatformSettingsService(session)
            ps = await settings_svc.load()

            if ps.schedule_publish_enabled:
                posts = await ProcessedPostRepository(session).list_scheduled_due()
                for post in posts:
                    publish_post_task.delay(post.id)
                result["publish_queued"] = len(posts)
                if posts:
                    logger.info("Scheduled publishes queued", count=len(posts))

            if ps.schedule_fetch_enabled:
                due = True
                if ps.scheduler_last_fetch_at is not None:
                    elapsed = now - ps.scheduler_last_fetch_at
                    due = elapsed >= timedelta(minutes=ps.fetch_interval_minutes)
                if due:
                    sources = await SourceRepository(session).list_active()
                    for source in sources:
                        fetch_source_task.delay(source.id, manual=False)
                    await settings_svc.mark_fetch_run(now)
                    result["fetch_sources_queued"] = len(sources)
                    logger.info(
                        "Scheduled fetch for sources",
                        count=len(sources),
                        interval_minutes=ps.fetch_interval_minutes,
                    )

            if ps.schedule_curated_publish_enabled:
                curated = await CuratedPublishService(session).run_due_topics()
                result["curated_queued"] = curated
                queued = [v for v in curated.values() if v is not None]
                if queued:
                    logger.info("Curated publish topics queued", picks=curated)

            if ps.schedule_article_publish_enabled:
                articles = await ArticleSchedulerService(session).run_due_channels()
                result["article_queued"] = articles
                if any(v is not None for v in articles.values()):
                    logger.info("Article generation channels queued", picks=articles)

            if ps.schedule_analytics_enabled:
                due = True
                if ps.scheduler_last_analytics_at is not None:
                    elapsed = now - ps.scheduler_last_analytics_at
                    due = elapsed >= timedelta(minutes=ps.analytics_interval_minutes)
                if due:
                    collect_all_channels_stats.delay()
                    await settings_svc.mark_analytics_run(now)
                    result["analytics_queued"] = True
                    logger.info(
                        "Scheduled analytics collection queued",
                        interval_minutes=ps.analytics_interval_minutes,
                    )

            if ps.schedule_retention_enabled:
                if (
                    now.hour == ps.retention_hour_utc
                    and now.minute == ps.retention_minute_utc
                ):
                    today = now.date().isoformat()
                    if ps.scheduler_last_retention_at != today:
                        app_settings = get_settings()
                        stats = await RetentionService(
                            session,
                            retention_days=app_settings.retention_days,
                            raw_posts_retention_days=ps.raw_posts_retention_days,
                        ).cleanup_expired()
                        await settings_svc.mark_retention_run(today)
                        result["retention_ran"] = True
                        logger.info(
                            "Scheduled retention finished",
                            publish_logs=stats.publish_logs,
                            background_jobs=stats.background_jobs,
                            raw_posts_unprocessed=stats.raw_posts_unprocessed,
                            raw_posts=stats.raw_posts,
                        )

            await session.commit()
        return result

    return run_async(_run())
