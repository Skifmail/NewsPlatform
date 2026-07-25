"""Сервис диагностики: здоровье конвейера публикаций для панели."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.pipeline_health import HealthVerdict, assess_pipeline
from app.infrastructure.models.background_job import BackgroundJob
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.app_error_log_repository import AppErrorLogRepository
from app.repositories.setting_repository import SettingRepository

# Активное окно публикаций: МСК 07:00–23:00 (UTC+3, без переходов).
_MSK_OFFSET = timedelta(hours=3)
_ACTIVE_START_HOUR = 7
_ACTIVE_END_HOUR = 23


@dataclass(frozen=True)
class ChannelPublishHealth:
    """Последняя публикация канала."""

    channel_id: int
    name: str
    last_published_at: datetime | None
    hours_since: float | None


@dataclass(frozen=True)
class PipelineHealth:
    """Полная сводка здоровья конвейера."""

    verdict: HealthVerdict
    last_publish_at: datetime | None
    last_fetch_at: datetime | None
    failed_jobs_24h: int
    errors_1h: int
    errors_24h: int
    in_active_window: bool
    channels: list[ChannelPublishHealth]


class DiagnosticsService:
    """Собирает сигналы здоровья из БД и выносит вердикт."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def pipeline_health(self) -> PipelineHealth:
        """Считает вердикт и метрики конвейера.

        Returns:
            PipelineHealth: агрегированное состояние.
        """
        now = datetime.now(UTC)

        last_publish_at = await self._last_publish_at()
        channels = await self._channels_health(now)
        last_fetch_at = await self._last_fetch_at()
        failed_jobs_24h = await self._failed_jobs_since(now - timedelta(hours=24))

        error_repo = AppErrorLogRepository(self._session)
        errors_1h = await error_repo.count_since(1)
        errors_24h = await error_repo.count_since(24)

        in_active_window = self._in_active_window(now)
        verdict = assess_pipeline(
            now=now,
            last_publish_at=last_publish_at,
            last_fetch_at=last_fetch_at,
            failed_jobs_24h=failed_jobs_24h,
            in_active_window=in_active_window,
        )
        return PipelineHealth(
            verdict=verdict,
            last_publish_at=last_publish_at,
            last_fetch_at=last_fetch_at,
            failed_jobs_24h=failed_jobs_24h,
            errors_1h=errors_1h,
            errors_24h=errors_24h,
            in_active_window=in_active_window,
            channels=channels,
        )

    def _in_active_window(self, now: datetime) -> bool:
        """True, если сейчас активное окно публикаций (МСК)."""
        msk_hour = (now + _MSK_OFFSET).hour
        return _ACTIVE_START_HOUR <= msk_hour < _ACTIVE_END_HOUR

    async def _last_publish_at(self) -> datetime | None:
        """Максимальный published_at по всем каналам."""
        result = await self._session.execute(
            select(func.max(ProcessedPost.published_at)).where(
                ProcessedPost.published_at.is_not(None)
            )
        )
        return result.scalar_one_or_none()

    async def _channels_health(self, now: datetime) -> list[ChannelPublishHealth]:
        """Последняя публикация по каждому активному каналу."""
        result = await self._session.execute(
            select(
                Channel.id,
                Channel.name,
                func.max(ProcessedPost.published_at),
            )
            .select_from(Channel)
            .outerjoin(ProcessedPost, ProcessedPost.channel_id == Channel.id)
            .group_by(Channel.id, Channel.name)
            .order_by(Channel.id)
        )
        items: list[ChannelPublishHealth] = []
        for channel_id, name, last_at in result.all():
            hours = None
            if last_at is not None:
                hours = max(0.0, (now - last_at).total_seconds() / 3600.0)
            items.append(
                ChannelPublishHealth(
                    channel_id=channel_id,
                    name=name,
                    last_published_at=last_at,
                    hours_since=hours,
                )
            )
        return items

    async def _last_fetch_at(self) -> datetime | None:
        """Время последнего парсинга из настроек планировщика."""
        raw = (
            await SettingRepository(self._session).get("scheduler_last_fetch_at", "")
        ).strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            return None

    async def _failed_jobs_since(self, cutoff: datetime) -> int:
        """Число упавших фоновых задач с момента cutoff."""
        result = await self._session.execute(
            select(func.count(BackgroundJob.id)).where(
                BackgroundJob.status == "failed",
                BackgroundJob.created_at >= cutoff,
            )
        )
        return int(result.scalar_one())
