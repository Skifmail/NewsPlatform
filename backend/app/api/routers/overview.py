"""Роутер обзорной панели (главная страница)."""

from fastapi import APIRouter, Query

from app.api.deps import AuthDep, DbSession
from app.api.schemas.overview import (
    AttentionItem,
    OverviewKpis,
    OverviewResponse,
    OverviewTrendPoint,
    PlatformStatus,
    RecentPublication,
    TopChannelItem,
    UpcomingPublication,
)
from app.services.overview_service import OverviewService

router = APIRouter(prefix="/overview", tags=["overview"])


@router.get("", response_model=OverviewResponse)
async def get_overview(
    session: DbSession,
    _: AuthDep,
    trend_period: str = Query("week", pattern="^(today|week|month|all)$"),
) -> OverviewResponse:
    """Агрегированные данные для главной страницы «Обзор»."""
    data = await OverviewService(session).get_overview(trend_period=trend_period)
    return OverviewResponse(
        kpis=OverviewKpis(
            subscribers_total=data.subscribers_total,
            subscribers_delta_today=data.subscribers_delta_today,
            publications_today_success=data.publications_today_success,
            publications_today_failed=data.publications_today_failed,
            total_views=data.total_views,
            queue_pending=data.queue_pending,
            approved_queue=data.approved_queue,
            active_jobs=data.active_jobs,
            materials_unprocessed=data.materials_unprocessed,
        ),
        attention=[
            AttentionItem(
                key=key,
                label=label,
                count=count,
                route=route,
                severity=severity,
            )
            for key, label, count, route, severity in data.attention
        ],
        upcoming=[
            UpcomingPublication(
                id=post_id,
                channel_id=channel_id,
                channel_name=channel_name,
                scheduled_at=scheduled_at,
                preview=preview,
            )
            for post_id, channel_id, channel_name, scheduled_at, preview in data.upcoming
        ],
        top_channels=[
            TopChannelItem(
                channel_id=channel_id,
                name=name,
                platform=platform,
                subscribers=subscribers,
                subscribers_delta=subscribers_delta,
                engagement_rate=engagement_rate,
                total_views=total_views,
            )
            for channel_id, name, platform, subscribers, subscribers_delta, engagement_rate, total_views in data.top_channels
        ],
        recent_publications=[
            RecentPublication(
                id=log_id,
                channel_name=channel_name,
                status=status,
                attempted_at=attempted_at,
                preview=preview,
            )
            for log_id, channel_name, status, attempted_at, preview in data.recent_publications
        ],
        trend=[
            OverviewTrendPoint(captured_at=captured_at, label=label, value=value)
            for captured_at, label, value in data.trend
        ],
        platform_status=PlatformStatus(
            schedule_fetch_enabled=data.schedule_fetch_enabled,
            schedule_publish_enabled=data.schedule_publish_enabled,
            schedule_ai_enabled=data.schedule_ai_enabled,
        ),
    )
