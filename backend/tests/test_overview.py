"""Тесты OverviewService."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.enums import PostStatus, PublishStatus
from app.infrastructure.models.channel import Channel
from app.services.channel_analytics_service import AnalyticsSummary, ChannelAnalyticsOverview
from app.services.overview_service import OverviewService


@pytest.fixture
def mock_session() -> MagicMock:
    """Мок async-сессии SQLAlchemy."""
    return MagicMock()


def _channel_overview(channel_id: int, name: str, subscribers: int) -> ChannelAnalyticsOverview:
    """Собирает тестовый обзор канала."""
    channel = Channel(
        id=channel_id,
        name=name,
        platform="telegram",
        platform_id=f"@ch{channel_id}",
        topic="it",
        is_active=True,
    )
    return ChannelAnalyticsOverview(
        channel=channel,
        subscribers=subscribers,
        subscribers_delta=10,
        subscribers_unsubscribed_total=0,
        posts_count=5,
        platform_posts_count=5,
        total_views=1000,
        avg_views=50.0,
        avg_reach=None,
        engagement_rate=5.0,
        publications_total=5,
        ad_integrations_count=0,
        ad_revenue_total=0.0,
        growth_points=[],
        last_collected_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_get_overview_aggregates_kpis(mock_session: MagicMock) -> None:
    """Обзор собирает KPI и блок внимания из репозиториев."""
    service = OverviewService(mock_session)
    service._analytics.get_summary = AsyncMock(
        return_value=AnalyticsSummary(
            channels_total=2,
            subscribers_total=1500,
            publications_total=40,
            total_views=12000,
            avg_views=80.0,
            ad_integrations_total=0,
            ad_revenue_total=0.0,
        )
    )
    service._analytics.list_channel_overviews = AsyncMock(
        return_value=[
            _channel_overview(1, "IT News", 1000),
            _channel_overview(2, "Auto", 500),
        ]
    )
    service._publish_logs.count_since_grouped_by_status = AsyncMock(
        return_value={
            PublishStatus.SUCCESS.value: 7,
            PublishStatus.FAILED.value: 1,
        }
    )
    service._posts.count_by_status = AsyncMock(
        side_effect=lambda status: 3 if status == PostStatus.PENDING else 2
    )
    service._posts.count_approved = AsyncMock(return_value=5)
    service._raw_posts.count_unprocessed = AsyncMock(return_value=12)
    service._jobs.count_by_status = AsyncMock(
        return_value={"queued": 1, "running": 2, "failed": 4}
    )
    service._snapshots.latest_before = AsyncMock(return_value=None)
    service._snapshots.latest_subscribers_snapshot = AsyncMock(return_value=None)
    service._posts.list_upcoming_scheduled = AsyncMock(return_value=[])
    service._publish_logs.list_history = AsyncMock(return_value=[])
    service._channels.list_all = AsyncMock(return_value=[])

    with patch(
        "app.services.overview_service.PlatformSettingsService"
    ) as settings_cls:
        settings_cls.return_value.get_public_merged = AsyncMock(
            return_value={
                "schedule_fetch_enabled": "true",
                "schedule_publish_enabled": "false",
                "schedule_ai_enabled": "true",
            }
        )
        data = await service.get_overview(trend_period="week")

    assert data.subscribers_total == 1500
    assert data.publications_today_success == 7
    assert data.publications_today_failed == 1
    assert data.queue_pending == 3
    assert data.active_jobs == 3
    assert data.materials_unprocessed == 12
    assert data.schedule_fetch_enabled is True
    assert data.schedule_publish_enabled is False
    keys = {item[0] for item in data.attention}
    assert "queue" in keys
    assert "materials" in keys
    assert "failed_jobs" in keys


def test_build_attention_empty_when_all_clear(mock_session: MagicMock) -> None:
    """Без проблем блок внимания пуст."""
    service = OverviewService(mock_session)
    attention = service._build_attention(
        queue_pending=0,
        failed_queue=0,
        materials_unprocessed=0,
        failed_jobs=0,
    )
    assert attention == []
