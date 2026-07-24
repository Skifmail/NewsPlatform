"""Единый планировщик: парсинг, публикация, retention по настройкам БД."""

from datetime import UTC, datetime, timedelta

from loguru import logger

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.source_repository import SourceRepository
from app.services.article_scheduler_service import ArticleSchedulerService
from app.services.curated_publish_service import CuratedPublishService
from app.services.platform_settings_service import PlatformSettingsService
from app.services.retention_service import RetentionService
from app.tasks.async_runner import run_async
from app.tasks.analytics_tasks import collect_all_channels_stats
from app.tasks.celery_app import celery_app
from app.tasks.fetch_tasks import fetch_source_task


@celery_app.task(name="app.tasks.scheduler_tasks.platform_scheduler_tick")
def platform_scheduler_tick() -> dict[str, int | bool]:
    """Раз в минуту проверяет настройки и запускает due-задачи.

    Returns:
        dict[str, int | bool]: счётчики и флаги срабатывания.
    """

    async def _run() -> dict[str, int | bool]:
        now = datetime.now(UTC)
        result: dict[str, int | bool | dict[str, int | None]] = {
            "channels_dispatched": {},
            "fetch_sources_queued": 0,
            "retention_ran": False,
            "curated_queued": {},
            "analytics_queued": False,
        }
        async with async_session_factory() as session:
            settings_svc = PlatformSettingsService(session)
            ps = await settings_svc.load()

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

            if ps.schedule_publish_enabled or ps.schedule_article_publish_enabled:
                dispatched = await ArticleSchedulerService(session).run_due_channels()
                result["channels_dispatched"] = dispatched
                fired = [cid for cid, v in dispatched.items() if v is not None]
                if fired:
                    logger.info("Channels dispatched", channel_ids=fired)

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

            # Ежечасный снимок баланса DeepSeek для истории расходов.
            from app.repositories.setting_repository import SettingRepository
            from app.services.ai_usage_service import AiUsageService

            setting_repo = SettingRepository(session)
            last_bal_raw = (await setting_repo.get("scheduler_last_balance_at", "")).strip()
            bal_due = True
            if last_bal_raw:
                try:
                    last_bal_at = datetime.fromisoformat(last_bal_raw)
                    bal_due = now - last_bal_at >= timedelta(minutes=60)
                except ValueError:
                    bal_due = True
            if bal_due:
                try:
                    await AiUsageService(session).snapshot_deepseek_balance()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("AI balance snapshot failed", error=str(exc))
                await setting_repo.set("scheduler_last_balance_at", now.isoformat())
                result["balance_snapshot"] = True

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
