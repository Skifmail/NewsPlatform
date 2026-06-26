"""Celery-задачи сбора аналитики каналов."""

from collections.abc import Callable

import redis
from celery import Task
from loguru import logger

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.channel_stats_snapshot import ChannelStatsSnapshot
from app.services.analytics_progress import RefreshProgressWriter
from app.services.channel_analytics_service import ChannelAnalyticsService
from app.tasks.async_runner import run_async
from app.tasks.celery_app import celery_app

_CHANNEL_LOCK_TIMEOUT_SEC = 120


def _channel_lock(channel_id: int) -> redis.lock.Lock:
    """Redis-lock на сбор статистики одного канала."""
    client = redis.from_url(get_settings().redis_url)
    return client.lock(
        f"lock:analytics:channel:{channel_id}",
        timeout=_CHANNEL_LOCK_TIMEOUT_SEC,
        blocking_timeout=0,
    )


def _snapshot_done(
    progress: RefreshProgressWriter,
) -> Callable[[Channel, bool, ChannelStatsSnapshot | None, str | None], None]:
    """Строит колбэк завершения канала, пишущий метрики из снимка в прогресс."""

    def _on_done(
        channel: Channel,
        success: bool,
        snapshot: ChannelStatsSnapshot | None,
        error: str | None,
    ) -> None:
        progress.mark_done(
            channel.id,
            success=success,
            subscribers=snapshot.subscribers if snapshot else None,
            posts=snapshot.posts_count if snapshot else None,
            total_views=snapshot.total_views if snapshot else None,
            error=error,
        )

    return _on_done


@celery_app.task(
    bind=True,
    name="app.tasks.analytics_tasks.collect_channel_stats_task",
)
def collect_channel_stats_task(self: Task, channel_id: int) -> dict[str, int | bool]:
    """Собирает статистику одного канала.

    Args:
        self: bound-задача (для task id прогресса).
        channel_id: ID канала.

    Returns:
        dict[str, int | bool]: результат сбора.
    """
    progress = RefreshProgressWriter(self.request.id)
    lock = _channel_lock(channel_id)
    if not lock.acquire(blocking=False):
        logger.info(
            "Analytics collection skipped: channel already in progress",
            channel_id=channel_id,
        )
        progress.init([(channel_id, f"Канал #{channel_id}", "")])
        progress.mark_done(
            channel_id,
            success=True,
            error="Сбор уже выполняется в другой задаче",
        )
        progress.finish(status="done")
        return {"channel_id": channel_id, "success": True, "skipped": True}

    async def _run() -> dict[str, int | bool]:
        async with async_session_factory() as session:
            service = ChannelAnalyticsService(session)
            channel = await service.channels.get_by_id(channel_id)
            if channel is not None:
                progress.init([(channel.id, channel.name, channel.platform)])
                progress.mark_running(channel.id)
            snapshot: ChannelStatsSnapshot | None = None
            error: str | None = None
            try:
                snapshot = await service.collect_channel(channel_id)
                await session.commit()
            except Exception as exc:
                error = str(exc)
                raise
            finally:
                if channel is not None:
                    progress.mark_done(
                        channel.id,
                        success=snapshot is not None and error is None,
                        subscribers=snapshot.subscribers if snapshot else None,
                        posts=snapshot.posts_count if snapshot else None,
                        total_views=snapshot.total_views if snapshot else None,
                        error=error,
                    )
                    progress.finish(status="done" if error is None else "error")
            return {
                "channel_id": channel_id,
                "success": snapshot is not None,
            }

    try:
        return run_async(_run())
    finally:
        try:
            lock.release()
        except redis.exceptions.LockNotOwnedError:
            pass


@celery_app.task(
    bind=True,
    name="app.tasks.analytics_tasks.collect_all_channels_stats",
)
def collect_all_channels_stats(self: Task) -> dict[str, int]:
    """Собирает статистику всех каналов.

    Args:
        self: bound-задача (для task id прогресса).

    Returns:
        dict[str, int]: счётчики успехов и ошибок.
    """
    progress = RefreshProgressWriter(self.request.id)

    async def _run() -> dict[str, int]:
        async with async_session_factory() as session:
            service = ChannelAnalyticsService(session)
            channels = await service.channels.list_all()
            progress.init(
                [(ch.id, ch.name, ch.platform) for ch in channels]
            )
            results = await service.collect_all_active(
                on_start=lambda ch: progress.mark_running(ch.id),
                on_done=_snapshot_done(progress),
            )
            await session.commit()
            success = sum(1 for ok in results.values() if ok)
            failed = sum(1 for ok in results.values() if not ok)
            progress.finish(status="done")
            logger.info(
                "Analytics collection finished",
                success=success,
                failed=failed,
            )
            return {
                "channels_total": len(results),
                "success": success,
                "failed": failed,
            }

    try:
        return run_async(_run())
    except Exception:
        progress.finish(status="error")
        raise
