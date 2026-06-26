"""Сервис модерации очереди постов."""

from datetime import datetime

from sqlalchemy import delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import BulkActionResponse
from app.api.schemas.post import QueueBulkFilters, QueueBulkRequest
from app.domain.enums import PostStatus
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.models.publish_log import PublishLog
from app.repositories.processed_post_repository import ProcessedPostRepository


class ModerationService:
    """Одобрение, отклонение и планирование постов."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._processed = ProcessedPostRepository(session)

    async def approve(
        self,
        post_id: int,
        rewritten_text: str | None = None,
        generated_image_url: str | None = None,
        publish_immediately: bool = False,
    ) -> ProcessedPost:
        """Одобряет пост.

        Args:
            post_id: ID processed_post.
            rewritten_text: отредактированный текст.
            generated_image_url: URL картинки.
            publish_immediately: сразу публиковать.

        Returns:
            ProcessedPost: обновлённый пост.

        Raises:
            ValueError: пост не найден.
        """
        post = await self._processed.get_by_id(post_id)
        if not post:
            msg = f"Post {post_id} not found"
            raise ValueError(msg)

        if rewritten_text:
            post.rewritten_text = rewritten_text
        if generated_image_url is not None:
            post.generated_image_url = generated_image_url
        post.status = PostStatus.APPROVED.value
        post.rejection_reason = None
        updated = await self._processed.update(post)

        if not publish_immediately:
            from app.services.scheduling_service import SchedulingService

            updated = await SchedulingService(self._session).assign_schedule_to_post(
                updated
            )

        await self._session.commit()

        if publish_immediately:
            from app.services.publish_service import PublishService

            await PublishService(self._session).publish_post(post_id)

        return updated

    async def reject(self, post_id: int, reason: str) -> ProcessedPost:
        """Отклоняет пост.

        Args:
            post_id: ID.
            reason: причина.

        Returns:
            ProcessedPost: обновлённый пост.

        Raises:
            ValueError: пост не найден.
        """
        post = await self._processed.get_by_id(post_id)
        if not post:
            msg = f"Post {post_id} not found"
            raise ValueError(msg)

        post.status = PostStatus.REJECTED.value
        post.rejection_reason = reason
        updated = await self._processed.update(post)
        await self._session.commit()
        return updated

    async def schedule(self, post_id: int, scheduled_at: datetime) -> ProcessedPost:
        """Планирует публикацию.

        Args:
            post_id: ID.
            scheduled_at: время.

        Returns:
            ProcessedPost: обновлённый пост.

        Raises:
            ValueError: пост не найден.
        """
        post = await self._processed.get_by_id(post_id)
        if not post:
            msg = f"Post {post_id} not found"
            raise ValueError(msg)

        post.status = PostStatus.APPROVED.value
        post.scheduled_at = scheduled_at
        updated = await self._processed.update(post)
        await self._session.commit()
        return updated

    async def update_content(
        self,
        post_id: int,
        rewritten_text: str | None = None,
        generated_image_url: str | None = None,
        scheduled_at: datetime | None = None,
    ) -> ProcessedPost:
        """Обновляет текст, картинку или время публикации одобренного поста.

        Args:
            post_id: ID processed_post.
            rewritten_text: новый текст.
            generated_image_url: URL картинки.
            scheduled_at: новое время публикации.

        Returns:
            ProcessedPost: обновлённый пост.

        Raises:
            ValueError: пост не найден или неверный статус.
        """
        post = await self._processed.get_by_id(post_id)
        if not post:
            msg = f"Post {post_id} not found"
            raise ValueError(msg)
        if post.status not in (
            PostStatus.APPROVED.value,
            PostStatus.PENDING.value,
            PostStatus.FAILED.value,
        ):
            msg = "Only pending, approved or failed posts can be edited"
            raise ValueError(msg)

        if rewritten_text is not None:
            post.rewritten_text = rewritten_text
        if generated_image_url is not None:
            post.generated_image_url = generated_image_url
        if scheduled_at is not None:
            post.scheduled_at = scheduled_at

        updated = await self._processed.update(post)
        await self._session.commit()
        return updated

    async def delete_post(self, post_id: int) -> None:
        """Удаляет пост (approved/pending/rejected).

        Args:
            post_id: ID.

        Raises:
            ValueError: пост не найден или уже опубликован.
        """
        post = await self._processed.get_by_id(post_id)
        if not post:
            msg = f"Post {post_id} not found"
            raise ValueError(msg)
        if post.status == PostStatus.PUBLISHED.value:
            msg = "Published posts cannot be deleted"
            raise ValueError(msg)

        from app.infrastructure.models.publish_log import PublishLog
        from sqlalchemy import delete as sa_delete

        await self._session.execute(
            sa_delete(PublishLog).where(PublishLog.processed_post_id == post_id)
        )
        deleted = await self._processed.delete_by_id(post_id)
        if not deleted:
            msg = f"Post {post_id} not found"
            raise ValueError(msg)
        await self._session.commit()

    async def bulk_queue_action(self, request: QueueBulkRequest) -> BulkActionResponse:
        """Массовое отклонение или удаление постов из очереди pending."""
        from datetime import UTC

        from sqlalchemy import update

        filters = request.filters or QueueBulkFilters()
        target_ids = await self._processed.list_pending_ids_for_bulk(
            post_ids=request.post_ids,
            channel_id=filters.channel_id,
            topic=filters.topic,
            older_than_days=filters.older_than_days,
        )
        skipped = 0
        if request.post_ids:
            skipped = len(set(request.post_ids) - set(target_ids))

        if request.dry_run:
            verb = "отклонено" if request.action == "reject" else "удалено"
            return BulkActionResponse(
                message=f"Будет {verb}: {len(target_ids)}",
                affected=len(target_ids),
                skipped=skipped,
                dry_run=True,
            )

        if not target_ids:
            return BulkActionResponse(
                message="Нет постов для обработки",
                affected=0,
                skipped=skipped,
            )

        reason = request.reason or "Массовое отклонение"
        now = datetime.now(UTC)

        if request.action == "reject":
            await self._session.execute(
                update(ProcessedPost)
                .where(
                    ProcessedPost.id.in_(target_ids),
                    ProcessedPost.status == PostStatus.PENDING.value,
                )
                .values(
                    status=PostStatus.REJECTED.value,
                    rejection_reason=reason,
                    updated_at=now,
                )
            )
            await self._session.commit()
            return BulkActionResponse(
                message=f"Отклонено: {len(target_ids)}",
                affected=len(target_ids),
                skipped=skipped,
            )

        await self._session.execute(
            sa_delete(PublishLog).where(
                PublishLog.processed_post_id.in_(target_ids)
            )
        )
        await self._session.execute(
            sa_delete(ProcessedPost).where(
                ProcessedPost.id.in_(target_ids),
                ProcessedPost.status == PostStatus.PENDING.value,
            )
        )
        await self._session.commit()
        return BulkActionResponse(
            message=f"Удалено: {len(target_ids)}",
            affected=len(target_ids),
            skipped=skipped,
        )
