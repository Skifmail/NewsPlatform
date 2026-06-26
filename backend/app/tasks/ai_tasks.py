"""Celery-задачи AI-обработки."""

from app.domain.ai_errors import DeepSeekAuthError
from app.infrastructure.database import async_session_factory
from app.services.job_execution import with_job_tracking
from app.services.job_tracker import _format_process_result
from app.services.process_service import ProcessService
from app.tasks.async_runner import run_async
from app.tasks.celery_app import celery_app


@celery_app.task(
    bind=True,
    name="app.tasks.ai_tasks.process_post",
    autoretry_for=(Exception,),
    dont_autoretry_for=(DeepSeekAuthError,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def process_post_task(self, raw_post_id: int, curated: bool = False) -> list[int]:
    """AI-обработка сырого поста.

    Args:
        raw_post_id: ID raw_post.
        curated: автопубликация после рерайта (лучшая новость по теме).

    Returns:
        list[int]: ID processed_posts.
    """

    task_id = self.request.id

    async def _work() -> object:
        async with async_session_factory() as session:
            return await ProcessService(session).process_raw_post(
                raw_post_id,
                curated=curated,
                celery_task_id=task_id,
            )

    async def _run() -> object:
        return await with_job_tracking(task_id, _format_process_result, _work)

    outcome = run_async(_run())
    from app.domain.process_result import ProcessResult

    if isinstance(outcome, ProcessResult):
        return outcome.created_ids
    return outcome
