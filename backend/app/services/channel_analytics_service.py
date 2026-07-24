"""Сервис сбора и агрегации аналитики каналов."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.ad_integration import AdIntegration
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.channel_stats_snapshot import ChannelStatsSnapshot
from app.infrastructure.models.max_member import MaxMember
from app.infrastructure.models.post_metric import PostMetric
from app.infrastructure.models.telegram_broadcast_stats import TelegramBroadcastStats
from app.infrastructure.stats.base import ChannelStatsDTO, PostMetricDTO
from app.infrastructure.stats.factory import get_stats_collector
from app.repositories.ad_integration_repository import AdIntegrationRepository
from app.repositories.channel_repository import ChannelRepository
from app.repositories.channel_stats_repository import ChannelStatsRepository
from app.repositories.max_member_repository import MaxMemberRepository
from app.repositories.post_metrics_repository import PostMetricsRepository
from app.repositories.publish_log_repository import PublishLogRepository
from app.repositories.telegram_broadcast_stats_repository import (
    TelegramBroadcastStatsRepository,
)
from app.services.chart_history import (
    build_chart_history,
    period_bounds,
    period_view_windows,
)

GROWTH_PERIODS = frozenset({"today", "week", "month", "all"})
GROWTH_OVERVIEW_LIMIT = 90
GROWTH_DOWNSAMPLE_THRESHOLD = 180


@dataclass(frozen=True)
class GrowthHistory:
    """История графика за выбранный период."""

    period: str
    metric: str
    granularity: str
    points: list[tuple[str, int | None]]
    period_total: int | None
    period_delta: int | None
    period_delta_percent: float | None
    previous_period_label: str | None
    subscribers_unsubscribed: int | None = None


def _sum_unsubscribes(snapshots: list[ChannelStatsSnapshot]) -> int | None:
    """Суммирует отписки по падениям между соседними снимками.

    Telegram не отдаёт точное число отписок; это сумма всех
    уменьшений счётчика между замерами.

    Args:
        snapshots: снимки от старых к новым.

    Returns:
        int | None: всего отписалось или None без данных.
    """
    if not snapshots:
        return None
    if len(snapshots) == 1:
        return 0

    total = 0
    has_value = False
    for index in range(1, len(snapshots)):
        previous = snapshots[index - 1].subscribers
        current = snapshots[index].subscribers
        if previous is None or current is None:
            continue
        has_value = True
        if current < previous:
            total += previous - current
    return total if has_value else None


def _snapshot_captured_at(snapshot: ChannelStatsSnapshot) -> datetime:
    """Нормализует captured_at снимка к UTC."""
    captured_at = snapshot.captured_at
    if captured_at.tzinfo is None:
        return captured_at.replace(tzinfo=UTC)
    return captured_at


def _subscribers_delta_since(
    snapshots: list[ChannelStatsSnapshot],
    since: datetime,
) -> int | None:
    """Прирост подписчиков с момента ``since`` до последнего снимка.

    Args:
        snapshots: снимки от старых к новым.
        since: нижняя граница окна (UTC).

    Returns:
        int | None: дельта подписчиков или None без данных.
    """
    if since.tzinfo is None:
        since = since.replace(tzinfo=UTC)

    before: list[ChannelStatsSnapshot] = []
    after: list[ChannelStatsSnapshot] = []
    for snapshot in snapshots:
        if snapshot.subscribers is None:
            continue
        if _snapshot_captured_at(snapshot) < since:
            before.append(snapshot)
        else:
            after.append(snapshot)

    if not after and not before:
        return None
    if not after:
        return 0

    start_value = before[-1].subscribers if before else after[0].subscribers
    end_value = after[-1].subscribers
    if start_value is None or end_value is None:
        return None
    return end_value - start_value


def _engagement_rate_from_views(
    views: int | None,
    subscribers: int | None,
) -> float | None:
    """ER = просмотры за период / подписчики × 100.

    Args:
        views: просмотры за окно (обычно 24ч).
        subscribers: текущее число подписчиков.

    Returns:
        float | None: ER в процентах или None без данных.
    """
    if views is None or subscribers is None or subscribers <= 0:
        return None
    return round((views / subscribers) * 100, 2)


def _endpoints_delta(
    snapshots: list[ChannelStatsSnapshot], attr: str
) -> int | None:
    """Разница значения метрики между первым и последним снимком.

    Args:
        snapshots: снимки от старых к новым.
        attr: имя числового поля снимка (``subscribers`` или ``total_views``).

    Returns:
        int | None: дельта за период или None, если данных недостаточно.
    """
    if len(snapshots) < 2:
        return None
    first = getattr(snapshots[0], attr)
    last = getattr(snapshots[-1], attr)
    if first is None or last is None:
        return None
    return last - first


def _downsample_daily(
    snapshots: list[ChannelStatsSnapshot],
) -> list[ChannelStatsSnapshot]:
    """Оставляет последний снимок каждого календарного дня.

    Args:
        snapshots: снимки от старых к новым.

    Returns:
        list[ChannelStatsSnapshot]: сжатая серия для графика.
    """
    by_day: dict[date, ChannelStatsSnapshot] = {}
    for snapshot in snapshots:
        day = snapshot.captured_at.date()
        existing = by_day.get(day)
        if existing is None or snapshot.captured_at > existing.captured_at:
            by_day[day] = snapshot
    return sorted(by_day.values(), key=lambda item: item.captured_at)


def _growth_since(period: str) -> datetime | None:
    """Нижняя граница периода для фильтра снимков.

    Args:
        period: today | week | month | all.

    Returns:
        datetime | None: since UTC или None для всей истории.
    """
    now = datetime.now(UTC)
    if period == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    return None


@dataclass(frozen=True)
class ChannelAnalyticsOverview:
    """Сводка по одному каналу для dashboard."""

    channel: Channel
    subscribers: int | None
    subscribers_delta: int | None
    subscribers_today: int | None
    subscribers_week: int | None
    subscribers_unsubscribed_total: int | None
    posts_count: int | None
    platform_posts_count: int | None
    total_views: int | None
    avg_views: float | None
    views_24h: int | None
    views_48h: int | None
    views_72h: int | None
    avg_reach: float | None
    engagement_rate: float | None
    publications_total: int
    ad_integrations_count: int
    ad_revenue_total: float
    growth_points: list[tuple[str, int | None]]
    last_collected_at: datetime | None


@dataclass(frozen=True)
class MaxMemberAnalytics:
    """Аналитика подписчиков MAX-канала на основе списка участников."""

    members_present: int
    joined_24h: int
    joined_7d: int
    joined_30d: int
    left_7d: int
    left_30d: int
    active_access_7d: int
    active_activity_24h: int
    admins_count: int
    joins_by_day: list[tuple[str, int]]
    recent_members: list["MaxMember"]


@dataclass(frozen=True)
class AnalyticsSummary:
    """Общая сводка по всем каналам."""

    channels_total: int
    subscribers_total: int
    publications_total: int
    total_views: int | None
    avg_views: float | None
    ad_integrations_total: int
    ad_revenue_total: float


class ChannelAnalyticsService:
    """Оркестрация сбора метрик и построение агрегатов."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._channels = ChannelRepository(session)
        self._snapshots = ChannelStatsRepository(session)
        self._post_metrics = PostMetricsRepository(session)
        self._publish_logs = PublishLogRepository(session)
        self._ads = AdIntegrationRepository(session)
        self._max_members = MaxMemberRepository(session)
        self._broadcast_stats = TelegramBroadcastStatsRepository(session)

    @property
    def channels(self) -> ChannelRepository:
        """Репозиторий каналов (для оркестрации прогресса в задачах)."""
        return self._channels

    async def collect_channel(self, channel_id: int) -> ChannelStatsSnapshot | None:
        """Собирает статистику одного канала с платформы.

        Args:
            channel_id: ID канала.

        Returns:
            ChannelStatsSnapshot | None: новый снимок или None если канал не найден.

        Raises:
            ValueError: канал не найден.
        """
        channel = await self._channels.get_by_id(channel_id)
        if not channel:
            msg = f"Channel {channel_id} not found"
            raise ValueError(msg)

        logs = await self._publish_logs.list_successful_by_channel(channel_id)
        known_post_ids = [
            log.platform_post_id for log in logs if log.platform_post_id
        ]
        log_by_post_id = {
            log.platform_post_id: log
            for log in logs
            if log.platform_post_id
        }

        collector = get_stats_collector(channel)
        try:
            stats = await collector.collect(channel, known_post_ids=known_post_ids)
        except Exception as exc:
            logger.warning(
                "Stats collector failed",
                channel_id=channel_id,
                platform=channel.platform,
                error=str(exc),
                exc_info=True,
            )
            stats = ChannelStatsDTO()

        now = datetime.now(UTC)
        for dto in stats.post_metrics:
            await self._upsert_post_metric(channel, dto, log_by_post_id, now)

        if stats.members:
            sync = await self._max_members.sync_channel_members(
                channel_id, stats.members
            )
            logger.info(
                "MAX members synced",
                channel_id=channel_id,
                total=sync.total_seen,
                new=sync.new_members,
                left=sync.left_members,
            )

        if stats.broadcast_stats is not None:
            await self._broadcast_stats.add_snapshot(
                channel_id, stats.broadcast_stats
            )
            logger.info(
                "Telegram broadcast stats stored",
                channel_id=channel_id,
                followers=stats.broadcast_stats.followers,
            )

        subscribers = stats.subscribers
        if subscribers is None:
            prev_sub = await self._snapshots.latest_subscribers_snapshot(channel_id)
            if prev_sub is not None:
                subscribers = prev_sub.subscribers

        snapshot = ChannelStatsSnapshot(
            channel_id=channel_id,
            subscribers=subscribers,
            posts_count=stats.posts_count,
            total_views=stats.total_views,
            captured_at=now,
        )
        saved = await self._snapshots.create(snapshot)
        logger.info(
            "Channel stats collected",
            channel_id=channel_id,
            subscribers=subscribers,
            posts=len(stats.post_metrics),
        )
        return saved

    async def collect_all_active(
        self,
        *,
        on_start: Callable[[Channel], None] | None = None,
        on_done: Callable[
            [Channel, bool, ChannelStatsSnapshot | None, str | None], None
        ]
        | None = None,
    ) -> dict[int, bool]:
        """Собирает статистику всех каналов.

        Args:
            on_start: колбэк перед опросом канала (для прогресса).
            on_done: колбэк после опроса канала
                ``(channel, success, snapshot, error)``.

        Returns:
            dict[int, bool]: channel_id → успех.
        """
        channels = await self._channels.list_all()
        results: dict[int, bool] = {}
        for channel in channels:
            if on_start is not None:
                on_start(channel)
            try:
                snapshot = await self.collect_channel(channel.id)
                results[channel.id] = True
                if on_done is not None:
                    on_done(channel, True, snapshot, None)
            except Exception as exc:
                logger.warning(
                    "Channel stats collection failed",
                    channel_id=channel.id,
                    error=str(exc),
                )
                results[channel.id] = False
                if on_done is not None:
                    on_done(channel, False, None, str(exc))
        return results

    async def get_summary(self) -> AnalyticsSummary:
        """Общая сводка по dashboard.

        Returns:
            AnalyticsSummary: агрегаты.
        """
        channels = await self._channels.list_all()
        subscribers_total = 0
        views_sum = 0.0
        views_count = 0
        total_views_sum = 0
        ad_total = 0
        revenue_total = 0.0

        for channel in channels:
            latest_sub = await self._snapshots.latest_subscribers_snapshot(channel.id)
            if latest_sub and latest_sub.subscribers:
                subscribers_total += latest_sub.subscribers
            agg = await self._post_metrics.aggregate_for_channel(channel.id)
            if agg["total_views"] is not None:
                total_views_sum += int(agg["total_views"])
            if agg["avg_views"] is not None and agg["posts_with_metrics"]:
                views_sum += float(agg["avg_views"]) * int(agg["posts_with_metrics"])
                views_count += int(agg["posts_with_metrics"])
            ad_total += await self._ads.count_for_channel(channel.id)
            revenue_total += await self._ads.sum_revenue_for_channel(channel.id)

        publications_total = await self._publish_logs.count_successful_all()
        avg_views = round(views_sum / views_count, 1) if views_count else None

        return AnalyticsSummary(
            channels_total=len(channels),
            subscribers_total=subscribers_total,
            publications_total=publications_total,
            total_views=total_views_sum or None,
            avg_views=avg_views,
            ad_integrations_total=ad_total,
            ad_revenue_total=round(revenue_total, 2),
        )

    async def get_channel_overview(self, channel_id: int) -> ChannelAnalyticsOverview:
        """Детальная сводка по каналу.

        Args:
            channel_id: ID канала.

        Returns:
            ChannelAnalyticsOverview: метрики канала.

        Raises:
            ValueError: канал не найден.
        """
        channel = await self._channels.get_by_id(channel_id)
        if not channel:
            msg = f"Channel {channel_id} not found"
            raise ValueError(msg)

        latest = await self._snapshots.latest_for_channel(channel_id)
        latest_sub = await self._snapshots.latest_subscribers_snapshot(channel_id)
        previous_sub = (
            await self._snapshots.previous_subscribers_snapshot(
                channel_id, latest_sub.captured_at
            )
            if latest_sub
            else None
        )
        history = await self._snapshots.list_for_channel(
            channel_id, limit=GROWTH_OVERVIEW_LIMIT
        )
        all_history = await self._snapshots.list_for_channel(channel_id, limit=None)
        agg = await self._post_metrics.aggregate_for_channel(channel_id)
        publications_total = await self._publish_logs.count_successful_by_channel(
            channel_id
        )
        ad_count = await self._ads.count_for_channel(channel_id)
        ad_revenue = await self._ads.sum_revenue_for_channel(channel_id)

        subscribers = latest_sub.subscribers if latest_sub else None
        subscribers_delta = None
        if (
            latest_sub
            and previous_sub
            and latest_sub.subscribers is not None
            and previous_sub.subscribers is not None
        ):
            subscribers_delta = latest_sub.subscribers - previous_sub.subscribers

        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = now - timedelta(days=7)
        views_24h, views_48h, views_72h = period_view_windows(all_history, now=now)
        # ER считаем по новым просмотрам за 24ч, а не по lifetime-среднему на пост.
        engagement_rate = _engagement_rate_from_views(views_24h, subscribers)

        growth_points = [
            (point.captured_at.isoformat(), point.subscribers) for point in history
        ]

        return ChannelAnalyticsOverview(
            channel=channel,
            subscribers=subscribers,
            subscribers_delta=subscribers_delta,
            subscribers_today=_subscribers_delta_since(all_history, today_start),
            subscribers_week=_subscribers_delta_since(all_history, week_start),
            subscribers_unsubscribed_total=_sum_unsubscribes(all_history),
            posts_count=publications_total,
            platform_posts_count=latest.posts_count if latest else None,
            total_views=agg["total_views"],
            avg_views=agg["avg_views"],
            views_24h=views_24h,
            views_48h=views_48h,
            views_72h=views_72h,
            avg_reach=agg["avg_reach"],
            engagement_rate=engagement_rate,
            publications_total=publications_total,
            ad_integrations_count=ad_count,
            ad_revenue_total=round(ad_revenue, 2),
            growth_points=growth_points,
            last_collected_at=latest.captured_at if latest else None,
        )

    async def get_member_analytics(self, channel_id: int) -> MaxMemberAnalytics:
        """Аналитика подписчиков MAX-канала из сохранённого списка участников.

        Args:
            channel_id: ID канала.

        Returns:
            MaxMemberAnalytics: агрегаты роста, оттока, активности и список.

        Raises:
            ValueError: канал не найден или не является MAX-каналом.
        """
        channel = await self._channels.get_by_id(channel_id)
        if not channel:
            msg = f"Channel {channel_id} not found"
            raise ValueError(msg)
        if channel.platform != "max":
            msg = "Member analytics available only for MAX channels"
            raise ValueError(msg)

        now = datetime.now(UTC)
        day = now - timedelta(days=1)
        week = now - timedelta(days=7)
        month = now - timedelta(days=30)
        repo = self._max_members

        return MaxMemberAnalytics(
            members_present=await repo.count_present(channel_id),
            joined_24h=await repo.count_joined_since(channel_id, day),
            joined_7d=await repo.count_joined_since(channel_id, week),
            joined_30d=await repo.count_joined_since(channel_id, month),
            left_7d=await repo.count_left_since(channel_id, week),
            left_30d=await repo.count_left_since(channel_id, month),
            active_access_7d=await repo.count_active_since(channel_id, week, by="access"),
            active_activity_24h=await repo.count_active_since(
                channel_id, day, by="activity"
            ),
            admins_count=sum(
                1
                for m in await repo.list_members(
                    channel_id, present_only=True, include_bots=True, limit=1000
                )
                if m.is_admin
            ),
            joins_by_day=await repo.joins_by_day(channel_id, month),
            recent_members=await repo.list_members(channel_id, limit=50),
        )

    async def get_broadcast_stats(self, channel_id: int) -> TelegramBroadcastStats | None:
        """Последний снимок нативной статистики Telegram-канала.

        Args:
            channel_id: ID канала.

        Returns:
            TelegramBroadcastStats | None: снимок или None, если статистика
            ещё не собиралась (канал мал / не Telegram / нет прав).

        Raises:
            ValueError: канал не найден.
        """
        channel = await self._channels.get_by_id(channel_id)
        if not channel:
            msg = f"Channel {channel_id} not found"
            raise ValueError(msg)
        return await self._broadcast_stats.latest_for_channel(channel_id)

    async def list_channel_overviews(self) -> list[ChannelAnalyticsOverview]:
        """Сводки по всем каналам.

        Returns:
            list[ChannelAnalyticsOverview]: обзоры.
        """
        channels = await self._channels.list_all()
        overviews: list[ChannelAnalyticsOverview] = []
        for channel in channels:
            try:
                overviews.append(await self.get_channel_overview(channel.id))
            except ValueError:
                continue
        return overviews

    async def get_growth_history(
        self,
        channel_id: int,
        period: str = "month",
        *,
        metric: str = "subscribers",
    ) -> GrowthHistory:
        """История графика за период с агрегацией по корзинам.

        Args:
            channel_id: ID канала.
            period: today | week | month | all.
            metric: subscribers (уровень) | views (прирост за корзину).

        Returns:
            GrowthHistory: точки графика и сравнение с прошлым периодом.

        Raises:
            ValueError: канал не найден, неверный period или metric.
        """
        if period not in GROWTH_PERIODS:
            msg = f"Invalid growth period: {period}"
            raise ValueError(msg)
        if metric not in {"subscribers", "views"}:
            msg = f"Invalid growth metric: {metric}"
            raise ValueError(msg)

        channel = await self._channels.get_by_id(channel_id)
        if not channel:
            msg = f"Channel {channel_id} not found"
            raise ValueError(msg)

        bounds = period_bounds(period)
        baseline = await self._snapshots.latest_before(channel_id, bounds.start)
        snapshots = await self._snapshots.list_for_channel(
            channel_id,
            since=bounds.previous_start if metric == "views" else bounds.start,
            limit=None,
        )
        if baseline and (not snapshots or snapshots[0].id != baseline.id):
            snapshots = [baseline, *snapshots]

        chart = build_chart_history(period, metric, snapshots)  # type: ignore[arg-type]

        return GrowthHistory(
            period=chart.period,
            metric=chart.metric,
            granularity=chart.granularity,
            points=chart.points,
            period_total=chart.period_total,
            period_delta=chart.period_delta,
            period_delta_percent=chart.period_delta_percent,
            previous_period_label=chart.previous_period_label,
            subscribers_unsubscribed=chart.subscribers_unsubscribed,
        )

    async def _upsert_post_metric(
        self,
        channel: Channel,
        dto: PostMetricDTO,
        log_by_post_id: dict[str, object],
        collected_at: datetime,
    ) -> PostMetric:
        """Сохраняет метрики поста с привязкой к publish_log."""
        log = log_by_post_id.get(dto.platform_post_id)
        processed_post_id = getattr(log, "processed_post_id", None) if log else None
        publish_log_id = getattr(log, "id", None) if log else None
        published_at = dto.published_at
        if published_at is None and log is not None:
            published_at = getattr(log, "published_at", None)

        metric = PostMetric(
            channel_id=channel.id,
            processed_post_id=processed_post_id,
            publish_log_id=publish_log_id,
            platform_post_id=dto.platform_post_id,
            post_url=dto.post_url,
            views=dto.views,
            forwards=dto.forwards,
            reactions=dto.reactions,
            comments=dto.comments,
            reach=dto.reach,
            reach_subscribers=dto.reach_subscribers,
            published_at=published_at,
            collected_at=collected_at,
        )
        return await self._post_metrics.upsert(metric)
