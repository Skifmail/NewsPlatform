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
        raw_posts_unprocessed: необработанные материалы старше raw_posts_retention_days.
        raw_posts: все материалы старше retention_days (processed_posts каскадом).
    """

    publish_logs: int = 0
    background_jobs: int = 0
    raw_posts_unprocessed: int = 0
    raw_posts: int = 0


class RetentionService:
    """Удаляет данные старше заданного срока хранения."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        retention_days: int = 30,
        raw_posts_retention_days: int = 3,
    ) -> None:
        self._session = session
        self._retention_days = max(1, retention_days)
        self._raw_posts_retention_days = max(1, raw_posts_retention_days)

    async def cleanup_expired(self) -> RetentionStats:
        """Удаляет записи по срокам хранения.

        Сначала — необработанные материалы (``raw_posts_retention_days``),
        затем общая очистка (``retention_days``).

        Returns:
            RetentionStats: число удалённых строк по таблицам.
        """
        now = datetime.now(UTC)
        stats = RetentionStats()

        unprocessed_cutoff = now - timedelta(days=self._raw_posts_retention_days)
        rp_unprocessed = await self._session.execute(
            delete(RawPost).where(
                RawPost.is_processed.is_(False),
                RawPost.fetched_at < unprocessed_cutoff,
            )
        )
        stats.raw_posts_unprocessed = rp_unprocessed.rowcount or 0

        cutoff = now - timedelta(days=self._retention_days)
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

        rp_result = await self._session.execute(
            delete(RawPost).where(RawPost.fetched_at < cutoff)
        )
        stats.raw_posts = rp_result.rowcount or 0

        await self._session.commit()
        logger.info(
            "Retention cleanup completed",
            retention_days=self._retention_days,
            raw_posts_retention_days=self._raw_posts_retention_days,
            unprocessed_cutoff=unprocessed_cutoff.isoformat(),
            cutoff=cutoff.isoformat(),
            publish_logs=stats.publish_logs,
            background_jobs=stats.background_jobs,
            raw_posts_unprocessed=stats.raw_posts_unprocessed,
            raw_posts=stats.raw_posts,
        )
        return stats
