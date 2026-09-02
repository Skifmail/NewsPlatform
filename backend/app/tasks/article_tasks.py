"""Celery-задачи генерации статей."""

from app.infrastructure.database import async_session_factory
from app.services.article_generation_service import ArticleGenerationService
from app.services.article_scheduler_recovery import release_article_scheduler_slot
from app.services.job_execution import with_job_tracking
from app.tasks.async_runner import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.tasks.article_tasks.generate_article",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def generate_article_task(
    self, channel_id: int, topic: str | None = None
) -> int:
    """Генерирует статью для article-канала.

    Args:
        channel_id: ID канала.
        topic: ручная тема/повод; None — ИИ выбирает сам.

    Returns:
        int: ID созданного processed_post.
    """

    task_id = self.request.id

    async def _work() -> int:
        async with async_session_factory() as session:
            return await ArticleGenerationService(session).generate_for_channel(
                channel_id,
                celery_task_id=task_id,
                topic=topic,
            )

    async def _run() -> int:
        return await with_job_tracking(
            task_id,
            lambda value: f"Статья создана: processed_post #{value}",
            _work,
        )

    try:
        return run_async(_run())
    except Exception:
        if self.request.retries >= self.max_retries:
            run_async(release_article_scheduler_slot(channel_id))
        raise
