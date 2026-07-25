"""Роутер окна диагностики: логи ошибок и здоровье конвейера."""

from fastapi import APIRouter

from app.api.deps import AuthDep, DbSession
from app.api.schemas.logs import (
    AppErrorLogResponse,
    ChannelPublishHealthResponse,
    PipelineHealthResponse,
)
from app.repositories.app_error_log_repository import AppErrorLogRepository
from app.services.diagnostics_service import DiagnosticsService

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("", response_model=list[AppErrorLogResponse])
async def list_logs(
    session: DbSession,
    _: AuthDep,
    level: str | None = None,
    since_hours: int | None = None,
    limit: int = 100,
) -> list[AppErrorLogResponse]:
    """Последние ошибки/предупреждения из всех процессов.

    Args:
        level: фильтр по уровню (ERROR/WARNING/CRITICAL) либо все.
        since_hours: только за последние N часов.
        limit: максимум записей (до 500).

    Returns:
        list[AppErrorLogResponse]: записи, новые сверху.
    """
    return await AppErrorLogRepository(session).list_recent(
        limit=limit, level=level, since_hours=since_hours
    )


@router.get("/health", response_model=PipelineHealthResponse)
async def pipeline_health(
    session: DbSession, _: AuthDep
) -> PipelineHealthResponse:
    """Здоровье конвейера публикаций (ловит «тихий» сбой).

    Returns:
        PipelineHealthResponse: статус, причина и метрики.
    """
    health = await DiagnosticsService(session).pipeline_health()
    return PipelineHealthResponse(
        status=health.verdict.status,
        reason=health.verdict.reason,
        last_publish_at=health.last_publish_at,
        last_fetch_at=health.last_fetch_at,
        failed_jobs_24h=health.failed_jobs_24h,
        errors_1h=health.errors_1h,
        errors_24h=health.errors_24h,
        in_active_window=health.in_active_window,
        channels=[
            ChannelPublishHealthResponse(
                channel_id=c.channel_id,
                name=c.name,
                last_published_at=c.last_published_at,
                hours_since=c.hours_since,
            )
            for c in health.channels
        ],
    )
