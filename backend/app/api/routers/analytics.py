"""Роутер аналитики каналов."""

from urllib.parse import quote

import json

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response

from app.api.deps import AuthDep, DbSession
from app.api.schemas.analytics import (
    AdIntegrationCreate,
    AdIntegrationResponse,
    AdIntegrationUpdate,
    AnalyticsSummaryResponse,
    ChannelAnalyticsResponse,
    GrowthHistoryResponse,
    GrowthPoint,
    ChartGrowthPoint,
    MaxMemberAnalyticsResponse,
    MaxMemberResponse,
    MemberJoinsPoint,
    PostMetricResponse,
    TelegramBroadcastStatsResponse,
    RefreshJobResponse,
    RefreshProgressResponse,
)
from app.api.schemas.common import MessageResponse
from app.infrastructure.models.ad_integration import AdIntegration
from app.repositories.ad_integration_repository import AdIntegrationRepository
from app.repositories.post_metrics_repository import PostMetricsRepository
from app.services.analytics_progress import read_progress
from app.services.channel_analytics_service import ChannelAnalyticsService
from app.domain.article_meta import parse_article_meta
from app.tasks.analytics_tasks import collect_all_channels_stats, collect_channel_stats_task

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _button_answer_clicks(
    raw: str | None,
    options_len: int,
) -> list[int] | None:
    """Преобразует JSON из `post_metrics.button_answers` в счётчики по option_idx."""
    if not options_len:
        return None

    if not raw:
        return [0 for _ in range(options_len)]

    try:
        data = json.loads(raw)
    except Exception:  # noqa: BLE001
        return [0 for _ in range(options_len)]

    if not isinstance(data, dict):
        return [0 for _ in range(options_len)]

    return [int(data.get(str(i), 0) or 0) for i in range(options_len)]


def _overview_to_response(overview) -> ChannelAnalyticsResponse:
    """Преобразует ChannelAnalyticsOverview в API-ответ."""
    return ChannelAnalyticsResponse(
        channel=overview.channel,
        subscribers=overview.subscribers,
        subscribers_delta=overview.subscribers_delta,
        subscribers_today=overview.subscribers_today,
        subscribers_week=overview.subscribers_week,
        subscribers_unsubscribed_total=overview.subscribers_unsubscribed_total,
        posts_count=overview.posts_count,
        platform_posts_count=overview.platform_posts_count,
        total_views=overview.total_views,
        avg_views=overview.avg_views,
        views_24h=overview.views_24h,
        views_48h=overview.views_48h,
        views_72h=overview.views_72h,
        avg_reach=overview.avg_reach,
        engagement_rate=overview.engagement_rate,
        publications_total=overview.publications_total,
        ad_integrations_count=overview.ad_integrations_count,
        ad_revenue_total=overview.ad_revenue_total,
        growth_points=[
            GrowthPoint(captured_at=ts, subscribers=subs)
            for ts, subs in overview.growth_points
        ],
        last_collected_at=overview.last_collected_at,
    )


@router.get("/summary", response_model=AnalyticsSummaryResponse)
async def get_analytics_summary(session: DbSession, _: AuthDep) -> AnalyticsSummaryResponse:
    """Общая сводка по активным каналам."""
    summary = await ChannelAnalyticsService(session).get_summary()
    return AnalyticsSummaryResponse(
        channels_total=summary.channels_total,
        subscribers_total=summary.subscribers_total,
        publications_total=summary.publications_total,
        total_views=summary.total_views,
        avg_views=summary.avg_views,
        ad_integrations_total=summary.ad_integrations_total,
        ad_revenue_total=summary.ad_revenue_total,
    )


@router.get("/channels", response_model=list[ChannelAnalyticsResponse])
async def list_channel_analytics(
    session: DbSession, _: AuthDep
) -> list[ChannelAnalyticsResponse]:
    """Сводки по всем каналам."""
    overviews = await ChannelAnalyticsService(session).list_channel_overviews()
    return [_overview_to_response(item) for item in overviews]


@router.get("/channels/{channel_id}", response_model=ChannelAnalyticsResponse)
async def get_channel_analytics(
    channel_id: int, session: DbSession, _: AuthDep
) -> ChannelAnalyticsResponse:
    """Детальная сводка по каналу."""
    try:
        overview = await ChannelAnalyticsService(session).get_channel_overview(channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _overview_to_response(overview)


@router.get("/channels/{channel_id}/growth", response_model=GrowthHistoryResponse)
async def get_channel_growth(
    channel_id: int,
    session: DbSession,
    _: AuthDep,
    period: str = Query("month", pattern="^(today|week|month|all)$"),
    metric: str = Query("subscribers", pattern="^(subscribers|views)$"),
) -> GrowthHistoryResponse:
    """История графика за период (подписчики или просмотры)."""
    try:
        history = await ChannelAnalyticsService(session).get_growth_history(
            channel_id, period=period, metric=metric
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GrowthHistoryResponse(
        period=history.period,
        metric=history.metric,
        granularity=history.granularity,
        points=[
            ChartGrowthPoint(captured_at=ts, value=val)
            for ts, val in history.points
        ],
        period_total=history.period_total,
        period_delta=history.period_delta,
        period_delta_percent=history.period_delta_percent,
        previous_period_label=history.previous_period_label,
        subscribers_unsubscribed=history.subscribers_unsubscribed,
    )


@router.get(
    "/channels/{channel_id}/members",
    response_model=MaxMemberAnalyticsResponse,
)
async def get_channel_member_analytics(
    channel_id: int, session: DbSession, _: AuthDep
) -> MaxMemberAnalyticsResponse:
    """Аналитика подписчиков MAX-канала: рост, отток, активность, список."""
    try:
        data = await ChannelAnalyticsService(session).get_member_analytics(channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return MaxMemberAnalyticsResponse(
        members_present=data.members_present,
        joined_24h=data.joined_24h,
        joined_7d=data.joined_7d,
        joined_30d=data.joined_30d,
        left_7d=data.left_7d,
        left_30d=data.left_30d,
        active_access_7d=data.active_access_7d,
        active_activity_24h=data.active_activity_24h,
        admins_count=data.admins_count,
        joins_by_day=[
            MemberJoinsPoint(day=day, count=count) for day, count in data.joins_by_day
        ],
        recent_members=[
            MaxMemberResponse.model_validate(m) for m in data.recent_members
        ],
    )


@router.get(
    "/channels/{channel_id}/telegram-stats",
    response_model=TelegramBroadcastStatsResponse | None,
)
async def get_channel_telegram_stats(
    channel_id: int, session: DbSession, _: AuthDep
) -> TelegramBroadcastStatsResponse | None:
    """Нативная статистика Telegram-канала; None, если ещё недоступна."""
    try:
        row = await ChannelAnalyticsService(session).get_broadcast_stats(channel_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if row is None:
        return None
    return TelegramBroadcastStatsResponse.model_validate(row)


@router.get("/channels/{channel_id}/posts", response_model=list[PostMetricResponse])
async def list_channel_post_metrics(
    channel_id: int,
    session: DbSession,
    _: AuthDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: str = Query(
        "published_at",
        pattern="^(views|published_at|reactions|forwards|comments|reach)$",
    ),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
) -> list[PostMetricResponse]:
    """Метрики постов канала."""
    try:
        metrics = await PostMetricsRepository(session).list_for_channel(
            channel_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    items: list[PostMetricResponse] = []
    for metric in metrics:
        post = metric.processed_post
        items.append(
            PostMetricResponse(
                id=metric.id,
                channel_id=metric.channel_id,
                processed_post_id=metric.processed_post_id,
                publish_log_id=metric.publish_log_id,
                platform_post_id=metric.platform_post_id,
                post_url=metric.post_url,
                views=metric.views,
                forwards=metric.forwards,
                reactions=metric.reactions,
                comments=metric.comments,
                reach=metric.reach,
                reach_subscribers=metric.reach_subscribers,
                published_at=metric.published_at,
                collected_at=metric.collected_at,
                rewritten_text=post.rewritten_text if post else None,
                post_text=metric.post_text,
                button_clicks=metric.button_clicks,
                button_options=(
                    parse_article_meta(post.article_meta).button_options
                    if post and post.article_meta
                    else None
                ),
                button_answer_clicks=(
                    _button_answer_clicks(metric.button_answers,
                        len(parse_article_meta(post.article_meta).button_options or [])
                    )
                    if post and post.article_meta
                    else None
                ),
            )
        )
    return items


@router.get("/channels/{channel_id}/posts/export")
async def export_channel_post_stats(
    channel_id: int,
    session: DbSession,
    _: AuthDep,
    days: int = Query(14, description="Период выгрузки: 14 или 30 дней"),
) -> Response:
    """Скачать CSV со статистикой постов за 14 или 30 дней."""
    try:
        filename, payload = await ChannelAnalyticsService(
            session
        ).export_channel_post_stats(channel_id, days)
    except ValueError as exc:
        detail = str(exc)
        code = (
            status.HTTP_404_NOT_FOUND
            if "not found" in detail.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=detail) from exc

    ascii_name = f"channel_stats_{days}d.csv"
    return Response(
        content=payload,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{ascii_name}"; '
                f"filename*=UTF-8''{quote(filename)}"
            ),
        },
    )


@router.post("/channels/{channel_id}/refresh", response_model=RefreshJobResponse)
async def refresh_channel_analytics(
    channel_id: int, session: DbSession, _: AuthDep
) -> RefreshJobResponse:
    """Ставит в очередь сбор статистики одного канала."""
    from app.repositories.channel_repository import ChannelRepository

    channel = await ChannelRepository(session).get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    result = collect_channel_stats_task.delay(channel_id)
    return RefreshJobResponse(
        message=f"Сбор статистики запущен (task {result.id})",
        job_id=result.id,
    )


@router.post("/refresh-all", response_model=RefreshJobResponse)
async def refresh_all_analytics(_: AuthDep) -> RefreshJobResponse:
    """Ставит в очередь сбор статистики всех каналов."""
    result = collect_all_channels_stats.delay()
    return RefreshJobResponse(
        message=f"Сбор статистики всех каналов запущен (task {result.id})",
        job_id=result.id,
    )


@router.get("/refresh-progress/{job_id}", response_model=RefreshProgressResponse)
async def get_refresh_progress(job_id: str, _: AuthDep) -> RefreshProgressResponse:
    """Возвращает прогресс задачи сбора статистики для всплывающего окна."""
    progress = await read_progress(job_id)
    if progress is None:
        raise HTTPException(status_code=404, detail="Прогресс не найден или устарел")
    return RefreshProgressResponse(**progress)


@router.get("/ads", response_model=list[AdIntegrationResponse])
async def list_ad_integrations(
    session: DbSession,
    _: AuthDep,
    channel_id: int | None = Query(None),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[AdIntegrationResponse]:
    """Список рекламных интеграций."""
    items = await AdIntegrationRepository(session).list_all(
        channel_id=channel_id, limit=limit, offset=offset
    )
    return [
        AdIntegrationResponse(
            id=item.id,
            channel_id=item.channel_id,
            processed_post_id=item.processed_post_id,
            platform_post_id=item.platform_post_id,
            post_url=item.post_url,
            advertiser=item.advertiser,
            price=item.price,
            currency=item.currency,
            placed_at=item.placed_at,
            status=item.status,
            note=item.note,
            created_at=item.created_at,
            channel=item.channel,
        )
        for item in items
    ]


@router.post("/ads", response_model=AdIntegrationResponse, status_code=status.HTTP_201_CREATED)
async def create_ad_integration(
    data: AdIntegrationCreate, session: DbSession, _: AuthDep
) -> AdIntegration:
    """Создаёт рекламную интеграцию."""
    from app.repositories.channel_repository import ChannelRepository

    channel = await ChannelRepository(session).get_by_id(data.channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")

    integration = AdIntegration(**data.model_dump())
    created = await AdIntegrationRepository(session).create(integration)
    await session.commit()
    await session.refresh(created)
    return created


@router.patch("/ads/{integration_id}", response_model=AdIntegrationResponse)
async def update_ad_integration(
    integration_id: int,
    data: AdIntegrationUpdate,
    session: DbSession,
    _: AuthDep,
) -> AdIntegration:
    """Обновляет рекламную интеграцию."""
    repo = AdIntegrationRepository(session)
    integration = await repo.get_by_id(integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Ad integration not found")

    payload = data.model_dump(exclude_unset=True)
    if "channel_id" in payload:
        from app.repositories.channel_repository import ChannelRepository

        channel = await ChannelRepository(session).get_by_id(payload["channel_id"])
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")

    for key, value in payload.items():
        setattr(integration, key, value)
    updated = await repo.update(integration)
    await session.commit()
    return updated


@router.delete("/ads/{integration_id}", response_model=MessageResponse)
async def delete_ad_integration(
    integration_id: int, session: DbSession, _: AuthDep
) -> MessageResponse:
    """Удаляет рекламную интеграцию."""
    repo = AdIntegrationRepository(session)
    integration = await repo.get_by_id(integration_id)
    if not integration:
        raise HTTPException(status_code=404, detail="Ad integration not found")
    await repo.delete(integration)
    await session.commit()
    return MessageResponse(message="Deleted")
