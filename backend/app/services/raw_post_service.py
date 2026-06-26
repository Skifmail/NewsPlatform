"""Постановка сырых постов на AI-обработку."""

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import BulkActionResponse
from app.api.schemas.raw_post import RawPostBulkDeleteRequest, RawPostBulkFilters
from app.domain.enums import Topic
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.models.publish_log import PublishLog
from app.repositories.raw_post_repository import RawPostRepository
from app.services.job_tracker import JobTracker
from app.tasks.ai_tasks import process_post_task

_CONTENT_PREVIEW_LEN = 280


def content_preview(text: str, max_len: int = _CONTENT_PREVIEW_LEN) -> str:
    """Обрезает текст для списка в панели.

    Args:
        text: полный контент.
        max_len: максимум символов.

    Returns:
        str: превью.
    """
    cleaned = " ".join(text.split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 1]}…"


class RawPostService:
    """Список материалов и запуск AI."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = RawPostRepository(session)
        self._tracker = JobTracker(session)

    async def enqueue_processing(
        self,
        raw_post_id: int,
    ) -> tuple[int, str] | None:
        """Ставит один сырой пост в очередь Celery AI.

        Args:
            raw_post_id: ID raw_post.

        Returns:
            tuple[int, str] | None: (job_id, celery_task_id) или None если пропуск.
        """
        raw = await self._repo.get_by_id(raw_post_id)
        if not raw:
            return None
        if raw.is_processed:
            children = await self._repo.count_processed_children(raw_post_id)
            if children > 0:
                return None
            await self._repo.unmark_processed(raw_post_id)
        result = process_post_task.delay(raw_post_id)
        job = await self._tracker.enqueue_process(result.id, raw_post_id)
        return job.id, result.id

    async def bulk_delete(self, request: RawPostBulkDeleteRequest) -> BulkActionResponse:
        """Массовое удаление сырых постов с учётом опубликованных дочерних постов."""
        filters = request.filters or RawPostBulkFilters()
        topic = Topic(filters.topic) if filters.topic else None
        deletable, skipped_ids = await self._repo.list_ids_for_bulk_delete(
            raw_post_ids=request.raw_post_ids,
            source_id=filters.source_id,
            topic=topic,
            is_processed=filters.is_processed,
            older_than_days=filters.older_than_days,
        )

        if request.dry_run:
            return BulkActionResponse(
                message=f"Будет удалено: {len(deletable)}",
                affected=len(deletable),
                skipped=len(skipped_ids),
                dry_run=True,
            )

        if not deletable:
            return BulkActionResponse(
                message="Нет материалов для удаления",
                affected=0,
                skipped=len(skipped_ids),
            )

        child_ids_result = await self._session.execute(
            select(ProcessedPost.id).where(ProcessedPost.raw_post_id.in_(deletable))
        )
        child_ids = [int(row[0]) for row in child_ids_result.all()]
        if child_ids:
            await self._session.execute(
                sa_delete(PublishLog).where(
                    PublishLog.processed_post_id.in_(child_ids)
                )
            )
        await self._repo.delete_by_ids(deletable)
        await self._session.commit()
        return BulkActionResponse(
            message=f"Удалено материалов: {len(deletable)}",
            affected=len(deletable),
            skipped=len(skipped_ids),
        )
