"""Сервис агрегации данных для обзорной панели."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import JobStatus, PostStatus, PublishStatus
from app.repositories.background_job_repository import BackgroundJobRepository
from app.repositories.channel_repository import ChannelRepository
from app.repositories.channel_stats_repository import ChannelStatsRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.publish_log_repository import PublishLogRepository
from app.repositories.raw_post_repository import RawPostRepository
from app.services.channel_analytics_service import (
    ChannelAnalyticsService,
    _downsample_daily,
    _growth_since,
)
from app.services.platform_settings_service import PlatformSettingsService


def _truncate_preview(text: str | None, limit: int = 120) -> str | None:
    """Обрезает HTML/текст для превью в виджетах.

    Args:
        text: исходный текст поста.
        limit: максимальная длина.

    Returns:
        str | None: короткий фрагмент без переносов.
    """
    if not text:
        return None
    cleaned = text.replace("\n", " ").strip()
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1]}…"


@dataclass(frozen=True)
class OverviewData:
    """Внутреннее представление обзорной панели."""

    subscribers_total: int
    subscribers_delta_today: int | None
    publications_today_success: int
    publications_today_failed: int
    total_views: int | None
    queue_pending: int
    approved_queue: int
    active_jobs: int
    materials_unprocessed: int
    attention: list[tuple[str, str, int, str, str]]
    top_channels: list[tuple[int, str, str, int | None, int | None, float | None, int | None]]
    recent_publications: list[tuple[int, str | None, str, datetime, str | None]]
    trend: list[tuple[str, str, int]]
    schedule_fetch_enabled: bool
    schedule_publish_enabled: bool
    schedule_ai_enabled: bool


class OverviewService:
    """Агрегирует метрики платформы для главной страницы."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._analytics = ChannelAnalyticsService(session)
        self._channels = ChannelRepository(session)
        self._snapshots = ChannelStatsRepository(session)
        self._posts = ProcessedPostRepository(session)
        self._publish_logs = PublishLogRepository(session)
        self._raw_posts = RawPostRepository(session)
        self._jobs = BackgroundJobRepository(session)

    async def get_overview(self, *, trend_period: str = "week") -> OverviewData:
        """Собирает все данные обзорной панели.

        Args:
            trend_period: today | week | month | all — период графика подписчиков.

        Returns:
            OverviewData: агрегированные метрики и виджеты.
        """
        summary = await self._analytics.get_summary()
        channel_overviews = await self._analytics.list_channel_overviews()

        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        pub_counts = await self._publish_logs.count_since_grouped_by_status(today_start)
        queue_pending = await self._posts.count_by_status(PostStatus.PENDING)
        approved_queue = await self._posts.count_approved()
        failed_queue = await self._posts.count_by_status(PostStatus.FAILED)
        materials_unprocessed = await self._raw_posts.count_unprocessed()
        job_counts = await self._jobs.count_by_status()
        active_jobs = job_counts.get(JobStatus.QUEUED.value, 0) + job_counts.get(
            JobStatus.RUNNING.value, 0
        )
        failed_jobs = job_counts.get(JobStatus.FAILED.value, 0)

        subscribers_delta_today = await self._subscribers_delta_today(channel_overviews)
        recent = await self._load_recent_publications()
        top_channels = self._build_top_channels(channel_overviews)
        trend = await self._aggregate_trend(trend_period)
        attention = self._build_attention(
            queue_pending=queue_pending,
            failed_queue=failed_queue,
            materials_unprocessed=materials_unprocessed,
            failed_jobs=failed_jobs,
        )

        settings = await PlatformSettingsService(self._session).get_public_merged()

        def _flag(key: str, default: bool = True) -> bool:
            value = settings.get(key, "true" if default else "false")
            return str(value).lower() in ("true", "1", "yes")

        return OverviewData(
            subscribers_total=summary.subscribers_total,
            subscribers_delta_today=subscribers_delta_today,
            publications_today_success=pub_counts.get(PublishStatus.SUCCESS.value, 0),
            publications_today_failed=pub_counts.get(PublishStatus.FAILED.value, 0),
            total_views=summary.total_views,
            queue_pending=queue_pending,
            approved_queue=approved_queue,
            active_jobs=active_jobs,
            materials_unprocessed=materials_unprocessed,
            attention=attention,
            top_channels=top_channels,
            recent_publications=recent,
            trend=trend,
            schedule_fetch_enabled=_flag("schedule_fetch_enabled"),
            schedule_publish_enabled=_flag("schedule_publish_enabled"),
            schedule_ai_enabled=_flag("schedule_ai_enabled"),
        )

    async def _subscribers_delta_today(
        self, overviews: list
    ) -> int | None:
        """Суммарный прирост подписчиков за сегодня по всем каналам."""
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        total_delta = 0
        has_data = False

        for overview in overviews:
            channel_id = overview.channel.id
            start_snap = await self._snapshots.latest_before(channel_id, today_start)
            if start_snap is None:
                start_snap = await self._snapshots.latest_subscribers_snapshot(channel_id)
            end_snap = await self._snapshots.latest_subscribers_snapshot(channel_id)
            if (
                start_snap
                and end_snap
                and start_snap.subscribers is not None
                and end_snap.subscribers is not None
            ):
                total_delta += end_snap.subscribers - start_snap.subscribers
                has_data = True

        return total_delta if has_data else None

    async def _load_recent_publications(
        self,
    ) -> list[tuple[int, str | None, str, datetime, str | None]]:
        """Последние попытки публикации."""
        logs = await self._publish_logs.list_history(limit=8)
        result: list[tuple[int, str | None, str, datetime, str | None]] = []
        for log in logs:
            channel_name = None
            preview = None
            if log.processed_post:
                if log.processed_post.channel:
                    channel_name = log.processed_post.channel.name
                preview = _truncate_preview(log.processed_post.rewritten_text)
            result.append(
                (
                    log.id,
                    channel_name,
                    log.status,
                    log.published_at,
                    preview,
                )
            )
        return result

    def _build_top_channels(self, overviews: list) -> list:
        """Топ-5 каналов по числу подписчиков."""
        sorted_channels = sorted(
            overviews,
            key=lambda item: item.subscribers or 0,
            reverse=True,
        )[:5]
        return [
            (
                item.channel.id,
                item.channel.name,
                item.channel.platform,
                item.subscribers,
                item.subscribers_delta,
                item.engagement_rate,
                item.total_views,
            )
            for item in sorted_channels
        ]

    def _build_attention(
        self,
        *,
        queue_pending: int,
        failed_queue: int,
        materials_unprocessed: int,
        failed_jobs: int,
    ) -> list[tuple[str, str, int, str, str]]:
        """Формирует список элементов, требующих внимания."""
        items: list[tuple[str, str, int, str, str]] = []
        if queue_pending > 0:
            items.append(
                (
                    "queue",
                    "Посты на модерации",
                    queue_pending,
                    "/queue",
                    "warning",
                )
            )
        if failed_queue > 0:
            items.append(
                (
                    "failed_publish",
                    "Ошибки публикации",
                    failed_queue,
                    "/approved",
                    "danger",
                )
            )
        if materials_unprocessed > 0:
            items.append(
                (
                    "materials",
                    "Материалы без обработки",
                    materials_unprocessed,
                    "/materials",
                    "info",
                )
            )
        if failed_jobs > 0:
            items.append(
                (
                    "failed_jobs",
                    "Задачи с ошибкой",
                    failed_jobs,
                    "/jobs",
                    "danger",
                )
            )
        return items

    async def _aggregate_trend(self, period: str) -> list[tuple[str, str, int]]:
        """Агрегирует тренд подписчиков по всем каналам."""
        since = _growth_since(period)
        channels = await self._channels.list_all()
        if not channels:
            return []

        by_day: dict[str, dict[int, int]] = {}

        for channel in channels:
            snapshots = await self._snapshots.list_for_channel(
                channel.id, since=since, limit=None
            )
            if not snapshots:
                continue
            if len(snapshots) > 180:
                snapshots = _downsample_daily(snapshots)
            for snapshot in snapshots:
                if snapshot.subscribers is None:
                    continue
                day_key = snapshot.captured_at.date().isoformat()
                day_bucket = by_day.setdefault(day_key, {})
                day_bucket[channel.id] = snapshot.subscribers

        if not by_day:
            return []

        points: list[tuple[str, str, int]] = []
        for day_key in sorted(by_day.keys()):
            total = sum(by_day[day_key].values())
            captured_at = f"{day_key}T00:00:00+00:00"
            label = datetime.fromisoformat(day_key).strftime("%d.%m")
            points.append((captured_at, label, total))

        return points
