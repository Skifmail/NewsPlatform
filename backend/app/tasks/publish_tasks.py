"""Celery-задачи публикации."""

from loguru import logger

from app.domain.enums import PostStatus
from app.infrastructure.database import async_session_factory
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.background_job_repository import BackgroundJobRepository
from app.services.job_execution import with_job_tracking
from app.services.job_tracker import JobTracker
from app.services.publish_service import PublishService
from app.tasks.async_runner import run_async
from app.domain.publish import PublishPermanentError
from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.tasks.publish_tasks.publish_post",
    autoretry_for=(Exception,),
    dont_autoretry_for=(PublishPermanentError, ValueError),
    retry_backoff=True,
    retry_backoff_max=600,
)
def publish_post_task(
    self, processed_post_id: int, bypass_daily_limit: bool = False
) -> int:
    """Публикует пост.

    Args:
        processed_post_id: ID processed_post.
        bypass_daily_limit: не проверять дневной лимит канала (умная публикация).

    Returns:
        int: ID publish_log.
    """
    task_id = self.request.id

    async def _work() -> int:
        async with async_session_factory() as session:
            repo = ProcessedPostRepository(session)
            jobs = BackgroundJobRepository(session)
            post = await repo.get_by_id(processed_post_id)
            if post and post.status == PostStatus.PENDING.value:
                post.status = PostStatus.APPROVED.value
                await repo.update(post)
            if not await jobs.get_by_celery_id(task_id):
                channel_name = post.channel.name if post and post.channel else "Канал"
                await JobTracker(session).enqueue_publish(
                    task_id, processed_post_id, channel_name
                )
            await session.commit()
            log = await PublishService(session).publish_post(
                processed_post_id,
                celery_task_id=task_id,
                bypass_daily_limit=bypass_daily_limit,
            )
            return log.id

    async def _run() -> int:
        return await with_job_tracking(
            task_id,
            lambda _: "Пост опубликован в канал",
            _work,
        )

    return run_async(_run())


