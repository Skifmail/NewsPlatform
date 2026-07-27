"""Тесты ChannelAnalyticsService с мок-коллектором."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.models.channel import Channel
from app.infrastructure.models.channel_stats_snapshot import ChannelStatsSnapshot
from app.infrastructure.stats.base import ChannelStatsDTO, PostMetricDTO
from app.services.channel_analytics_service import (
    ChannelAnalyticsService,
    _downsample_daily,
    _engagement_rate_from_views,
    _subscribers_delta_since,
    _sum_unsubscribes,
)


@pytest.fixture
def channel() -> Channel:
    """Тестовый канал."""
    ch = Channel(
        id=1,
        name="Test TG",
        platform="telegram",
        platform_id="@test",
        topic="it",
        is_active=True,
    )
    return ch


@pytest.fixture
def mock_session() -> MagicMock:
    """Мок async-сессии SQLAlchemy."""
    return MagicMock()


@pytest.mark.asyncio
async def test_collect_channel_creates_snapshot(
    mock_session: MagicMock, channel: Channel
) -> None:
    """Сбор статистики сохраняет снимок и метрики постов."""
    stats_dto = ChannelStatsDTO(
        subscribers=1000,
        posts_count=2,
        total_views=500,
        post_metrics=[
            PostMetricDTO(
                platform_post_id="10",
                post_url="https://t.me/test/10",
                views=300,
                forwards=5,
                reactions=12,
            )
        ],
    )

    mock_collector = AsyncMock()
    mock_collector.collect = AsyncMock(return_value=stats_dto)

    service = ChannelAnalyticsService(mock_session)
    service._channels.get_by_id = AsyncMock(return_value=channel)
    service._publish_logs.list_successful_by_channel = AsyncMock(return_value=[])
    service._post_metrics.upsert = AsyncMock(
        side_effect=lambda metric: metric
    )
    service._snapshots.create = AsyncMock(
        side_effect=lambda snap: snap
    )

    with patch(
        "app.services.channel_analytics_service.get_stats_collector",
        return_value=mock_collector,
    ):
        snapshot = await service.collect_channel(1)

    assert snapshot is not None
    assert snapshot.subscribers == 1000
    assert snapshot.total_views == 500
    service._post_metrics.upsert.assert_awaited_once()
    service._snapshots.create.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_summary_aggregates_channels(mock_session: MagicMock) -> None:
    """Сводка суммирует подписчиков и публикации."""
    ch1 = Channel(id=1, name="A", platform="telegram", platform_id="@a", topic="it")
    ch2 = Channel(id=2, name="B", platform="vk", platform_id="-1", topic="it")

    service = ChannelAnalyticsService(mock_session)
    service._channels.list_active = AsyncMock(return_value=[ch1, ch2])
    service._snapshots.latest_subscribers_snapshot = AsyncMock(
        side_effect=[
            ChannelStatsSnapshot(
                channel_id=1,
                subscribers=100,
                posts_count=10,
                total_views=1000,
                captured_at=datetime.now(UTC),
            ),
            ChannelStatsSnapshot(
                channel_id=2,
                subscribers=200,
                posts_count=20,
                total_views=2000,
                captured_at=datetime.now(UTC),
            ),
        ]
    )
    service._post_metrics.aggregate_for_channel = AsyncMock(
        return_value={
            "avg_views": 50.0,
            "total_views": 1000,
            "posts_with_views": 20,
            "avg_reach": None,
            "posts_with_metrics": 2,
        }
    )
    service._ads.count_for_channel = AsyncMock(return_value=1)
    service._ads.sum_revenue_for_channel = AsyncMock(return_value=500.0)
    service._publish_logs.count_successful_all = AsyncMock(return_value=15)

    summary = await service.get_summary()

    assert summary.channels_total == 2
    assert summary.subscribers_total == 300
    assert summary.publications_total == 15
    assert summary.ad_integrations_total == 2
    assert summary.ad_revenue_total == 1000.0
    service._channels.list_active.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_channel_overviews_active_sorted_by_subscribers(
    mock_session: MagicMock,
) -> None:
    """Список аналитики — только активные, по убыванию подписчиков."""
    from app.services.channel_analytics_service import ChannelAnalyticsOverview

    ch_small = Channel(
        id=1, name="Small", platform="telegram", platform_id="@s", topic="it"
    )
    ch_big = Channel(
        id=2, name="Big", platform="telegram", platform_id="@b", topic="it"
    )
    ch_none = Channel(
        id=3, name="None", platform="vk", platform_id="-1", topic="it"
    )

    overview_small = MagicMock(spec=ChannelAnalyticsOverview)
    overview_small.subscribers = 10
    overview_big = MagicMock(spec=ChannelAnalyticsOverview)
    overview_big.subscribers = 100
    overview_none = MagicMock(spec=ChannelAnalyticsOverview)
    overview_none.subscribers = None

    service = ChannelAnalyticsService(mock_session)
    service._channels.list_active = AsyncMock(
        return_value=[ch_small, ch_big, ch_none]
    )
    service.get_channel_overview = AsyncMock(
        side_effect=[overview_small, overview_big, overview_none]
    )

    result = await service.list_channel_overviews()

    assert [item.subscribers for item in result] == [100, 10, None]
    service._channels.list_active.assert_awaited_once()


def test_downsample_daily_keeps_last_snapshot_per_day() -> None:
    """Сжатие истории оставляет один снимок на календарный день."""
    base = datetime(2025, 1, 1, tzinfo=UTC)
    snapshots = [
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=100,
            captured_at=base.replace(hour=8),
        ),
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=110,
            captured_at=base.replace(hour=20),
        ),
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=120,
            captured_at=base.replace(day=2, hour=9),
        ),
    ]
    result = _downsample_daily(snapshots)
    assert len(result) == 2
    assert result[0].subscribers == 110
    assert result[1].subscribers == 120


@pytest.mark.asyncio
async def test_get_growth_history_filters_by_period(
    mock_session: MagicMock, channel: Channel
) -> None:
    """История роста фильтруется по period и возвращает агрегированные точки."""
    now = datetime.now(UTC)
    snapshots = [
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=100,
            captured_at=now.replace(day=max(1, now.day - 2)),
        ),
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=150,
            captured_at=now,
        ),
    ]

    service = ChannelAnalyticsService(mock_session)
    service._channels.get_by_id = AsyncMock(return_value=channel)
    service._snapshots.latest_before = AsyncMock(return_value=None)
    service._snapshots.list_for_channel = AsyncMock(return_value=snapshots)

    history = await service.get_growth_history(1, period="week")

    assert history.period == "week"
    assert history.metric == "subscribers"
    assert history.granularity == "day"
    assert history.period_total == 150
    service._snapshots.list_for_channel.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_growth_history_views_metric(
    mock_session: MagicMock, channel: Channel
) -> None:
    """Метрика views возвращает прирост просмотров, не накопительный total."""
    now = datetime.now(UTC)
    snapshots = [
        ChannelStatsSnapshot(
            channel_id=1,
            total_views=500,
            captured_at=now - timedelta(days=2),
        ),
        ChannelStatsSnapshot(
            channel_id=1,
            total_views=1700,
            captured_at=now,
        ),
    ]

    service = ChannelAnalyticsService(mock_session)
    service._channels.get_by_id = AsyncMock(return_value=channel)
    service._snapshots.latest_before = AsyncMock(return_value=None)
    service._snapshots.list_for_channel = AsyncMock(return_value=snapshots)

    history = await service.get_growth_history(1, period="week", metric="views")

    assert history.metric == "views"
    assert history.period_total == 1200


def test_sum_unsubscribes_counts_drops() -> None:
    """Суммируются только падения между снимками."""
    base = datetime(2025, 1, 1, tzinfo=UTC)
    snapshots = [
        ChannelStatsSnapshot(channel_id=1, subscribers=100, captured_at=base),
        ChannelStatsSnapshot(
            channel_id=1, subscribers=105, captured_at=base.replace(day=2)
        ),
        ChannelStatsSnapshot(
            channel_id=1, subscribers=103, captured_at=base.replace(day=3)
        ),
        ChannelStatsSnapshot(
            channel_id=1, subscribers=98, captured_at=base.replace(day=4)
        ),
    ]
    assert _sum_unsubscribes(snapshots) == 7


def test_sum_unsubscribes_single_snapshot() -> None:
    """Один снимок — отписок пока не было."""
    assert (
        _sum_unsubscribes(
            [
                ChannelStatsSnapshot(
                    channel_id=1,
                    subscribers=50,
                    captured_at=datetime.now(UTC),
                )
            ]
        )
        == 0
    )


def test_engagement_rate_from_24h_views() -> None:
    """ER считается от суточных просмотров, не от lifetime avg."""
    assert _engagement_rate_from_views(15, 14) == 107.14
    assert _engagement_rate_from_views(None, 14) is None
    assert _engagement_rate_from_views(15, 0) is None


def test_subscribers_delta_since_today() -> None:
    """Прирост подписчиков с начала дня относительно последнего снимка до окна."""
    now = datetime(2026, 7, 13, 15, 0, tzinfo=UTC)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    snapshots = [
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=11,
            captured_at=today_start - timedelta(hours=2),
        ),
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=12,
            captured_at=today_start + timedelta(hours=3),
        ),
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=14,
            captured_at=now,
        ),
    ]
    assert _subscribers_delta_since(snapshots, today_start) == 3


@pytest.mark.asyncio
async def test_get_channel_overview_uses_period_metrics(
    mock_session: MagicMock, channel: Channel
) -> None:
    """Сводка канала отдаёт окна просмотров и ER от 24ч."""
    now = datetime.now(UTC)
    snapshots = [
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=14,
            total_views=100,
            posts_count=10,
            captured_at=now - timedelta(hours=30),
        ),
        ChannelStatsSnapshot(
            channel_id=1,
            subscribers=14,
            total_views=115,
            posts_count=10,
            captured_at=now - timedelta(hours=2),
        ),
    ]
    latest = snapshots[-1]

    service = ChannelAnalyticsService(mock_session)
    service._channels.get_by_id = AsyncMock(return_value=channel)
    service._snapshots.latest_for_channel = AsyncMock(return_value=latest)
    service._snapshots.latest_subscribers_snapshot = AsyncMock(return_value=latest)
    service._snapshots.previous_subscribers_snapshot = AsyncMock(return_value=snapshots[0])
    service._snapshots.list_for_channel = AsyncMock(return_value=snapshots)
    service._post_metrics.aggregate_for_channel = AsyncMock(
        return_value={
            "avg_views": 66.4,
            "total_views": 5376,
            "posts_with_views": 80,
            "avg_reach": None,
            "posts_with_metrics": 80,
        }
    )
    service._publish_logs.count_successful_by_channel = AsyncMock(return_value=83)
    service._ads.count_for_channel = AsyncMock(return_value=0)
    service._ads.sum_revenue_for_channel = AsyncMock(return_value=0.0)

    overview = await service.get_channel_overview(1)

    assert overview.views_24h == 15
    assert overview.engagement_rate == 107.14
    assert overview.avg_views == 66.4
    assert overview.total_views == 5376


@pytest.mark.asyncio
async def test_get_growth_history_today_period(
    mock_session: MagicMock, channel: Channel
) -> None:
    """Период today фильтрует с начала календарного дня UTC."""
    service = ChannelAnalyticsService(mock_session)
    service._channels.get_by_id = AsyncMock(return_value=channel)
    service._snapshots.latest_before = AsyncMock(return_value=None)
    service._snapshots.list_for_channel = AsyncMock(return_value=[])

    history = await service.get_growth_history(1, period="today")

    assert history.period == "today"
    _, kwargs = service._snapshots.list_for_channel.await_args
    since = kwargs["since"]
    assert since.hour == 0 and since.minute == 0


@pytest.mark.asyncio
async def test_get_growth_history_invalid_period(
    mock_session: MagicMock, channel: Channel
) -> None:
    """Неверный period вызывает ValueError."""
    service = ChannelAnalyticsService(mock_session)
    service._channels.get_by_id = AsyncMock(return_value=channel)

    with pytest.raises(ValueError, match="Invalid growth period"):
        await service.get_growth_history(1, period="year")
