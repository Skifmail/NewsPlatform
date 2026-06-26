"""Очистка устаревших записей в БД."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.background_job import BackgroundJob
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.models.publish_log import PublishLog
from app.infrastructure.models.raw_post import RawPost


@dataclass
class RetentionStats:
    """Счётчики удалённых строк.

    Args:
        publish_logs: записи publish_log.
        background_jobs: записи background_jobs.
        raw_posts: сырые посты (processed_posts каскадом).
    """

    publish_logs: int = 0
    background_jobs: int = 0
    raw_posts: int = 0


class RetentionService:
    """Удаляет данные старше заданного срока хранения."""

    def __init__(self, session: AsyncSession, retention_days: int = 30) -> None:
        self._session = session
        self._retention_days = retention_days

    async def cleanup_expired(self) -> RetentionStats:
        """Удаляет записи старше ``retention_days`` дней.

        Returns:
            RetentionStats: число удалённых строк по таблицам.
        """
        cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)
        stats = RetentionStats()

        # Логи публикаций и задач, привязанные к старым processed_posts
        old_processed_ids = select(ProcessedPost.id).where(
            ProcessedPost.created_at < cutoff
        )
        pl_result = await self._session.execute(
            delete(PublishLog).where(
                (PublishLog.published_at < cutoff)
                | PublishLog.processed_post_id.in_(old_processed_ids)
            )
        )
        stats.publish_logs = pl_result.rowcount or 0

        bj_result = await self._session.execute(
            delete(BackgroundJob).where(BackgroundJob.created_at < cutoff)
        )
        stats.background_jobs = bj_result.rowcount or 0

        # Каскадно удалит processed_posts
        rp_result = await self._session.execute(
            delete(RawPost).where(RawPost.fetched_at < cutoff)
        )
        stats.raw_posts = rp_result.rowcount or 0

        await self._session.commit()
        logger.info(
            "Retention cleanup completed",
            retention_days=self._retention_days,
            cutoff=cutoff.isoformat(),
            publish_logs=stats.publish_logs,
            background_jobs=stats.background_jobs,
            raw_posts=stats.raw_posts,
        )
        return stats
