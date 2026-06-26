"""Учёт статусов Celery-задач для панели."""

from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import JobStatus, JobType
from app.domain.job_stage import encode_stage
from app.infrastructure.models.background_job import BackgroundJob
from app.repositories.background_job_repository import BackgroundJobRepository
from app.services.activity_notifier import notify_job
from app.tasks.async_runner import run_async


class JobTracker:
    """Создание и обновление записей о фоновых задачах."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = BackgroundJobRepository(session)
        self._session = session

    async def enqueue_fetch(
        self,
        celery_task_id: str,
        source_id: int,
        source_name: str,
    ) -> BackgroundJob:
        """Регистрирует задачу парсинга источника.

        Args:
            celery_task_id: ID задачи Celery.
            source_id: ID источника.
            source_name: название для UI.

        Returns:
            BackgroundJob: созданная запись.
        """
        job = BackgroundJob(
            celery_task_id=celery_task_id,
            job_type=JobType.FETCH.value,
            status=JobStatus.QUEUED.value,
            label=f"Парсинг: {source_name}",
            source_id=source_id,
        )
        created = await self._repo.create(job)
        await self._notify(created)
        return created

    async def enqueue_publish(
        self,
        celery_task_id: str,
        processed_post_id: int,
        channel_name: str,
    ) -> BackgroundJob:
        """Регистрирует задачу публикации.

        Args:
            celery_task_id: ID задачи Celery.
            processed_post_id: ID processed_post.
            channel_name: название канала для UI.

        Returns:
            BackgroundJob: созданная запись.
        """
        job = BackgroundJob(
            celery_task_id=celery_task_id,
            job_type=JobType.PUBLISH.value,
            status=JobStatus.QUEUED.value,
            label=f"Публикация: {channel_name}",
            raw_post_id=None,
        )
        created = await self._repo.create(job)
        await self._notify(created)
        return created

    async def enqueue_process(
        self,
        celery_task_id: str,
        raw_post_id: int,
        parent_celery_task_id: str | None = None,
        *,
        label: str | None = None,
        result_summary: str | None = None,
    ) -> BackgroundJob:
        """Регистрирует задачу AI-обработки.

        Args:
            celery_task_id: ID задачи Celery.
            raw_post_id: ID сырого поста.
            parent_celery_task_id: ID родительской задачи парсинга.
            label: подпись для панели (по умолчанию — AI-обработка).
            result_summary: предзаполненный итог (например, причина выбора).

        Returns:
            BackgroundJob: созданная запись.
        """
        job = BackgroundJob(
            celery_task_id=celery_task_id,
            job_type=JobType.PROCESS.value,
            status=JobStatus.QUEUED.value,
            label=label or f"AI-обработка поста #{raw_post_id}",
            raw_post_id=raw_post_id,
            parent_celery_task_id=parent_celery_task_id,
            result_summary=result_summary,
        )
        created = await self._repo.create(job)
        await self._notify(created)
        return created

    async def enqueue_article(
        self,
        celery_task_id: str,
        channel_id: int,
        channel_name: str,
    ) -> BackgroundJob:
        """Регистрирует задачу генерации статьи.

        Args:
            celery_task_id: ID задачи Celery.
            channel_id: ID канала.
            channel_name: название для UI.

        Returns:
            BackgroundJob: созданная запись.
        """
        job = BackgroundJob(
            celery_task_id=celery_task_id,
            job_type=JobType.ARTICLE.value,
            status=JobStatus.QUEUED.value,
            label=f"Статья: {channel_name}",
            # source_id — только FK на sources; канал указан в label.
            source_id=None,
        )
        created = await self._repo.create(job)
        await self._notify(created)
        return created

    async def _notify(self, job: BackgroundJob) -> None:
        """Отправляет WebSocket-событие о задаче.

        Args:
            job: запись background_jobs.
        """
        try:
            await notify_job(job)
        except Exception as exc:
            logger.warning("Activity notify failed", job_id=job.id, error=str(exc))

    async def update_stage(
        self,
        celery_task_id: str,
        detail: str,
        progress: int,
    ) -> None:
        """Обновляет текущий этап running-задачи для toast и панели.

        Args:
            celery_task_id: ID задачи Celery.
            detail: описание этапа для UI.
            progress: процент 0–100.
        """
        job = await self._repo.get_by_celery_id(celery_task_id)
        if not job or job.status != JobStatus.RUNNING.value:
            return
        job.result_summary = encode_stage(progress, detail)
        await self._repo.update(job)
        await self._notify(job)

    async def mark_running(self, celery_task_id: str) -> None:
        """Переводит задачу в статус running.

        Args:
            celery_task_id: ID задачи Celery.
        """
        job = await self._repo.get_by_celery_id(celery_task_id)
        if not job or job.status in (
            JobStatus.SUCCESS.value,
            JobStatus.FAILED.value,
            JobStatus.RUNNING.value,
        ):
            return
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        await self._repo.update(job)
        await self._notify(job)

    async def mark_success(
        self,
        celery_task_id: str,
        result_summary: str | None = None,
    ) -> None:
        """Завершает задачу успешно.

        Args:
            celery_task_id: ID задачи Celery.
            result_summary: краткий итог для панели.
        """
        job = await self._repo.get_by_celery_id(celery_task_id)
        if not job:
            return
        job.status = JobStatus.SUCCESS.value
        job.finished_at = datetime.now(UTC)
        if result_summary:
            job.result_summary = result_summary
        await self._repo.update(job)
        await self._notify(job)

    async def mark_failed(
        self,
        celery_task_id: str,
        error_message: str,
    ) -> None:
        """Завершает задачу с ошибкой.

        Args:
            celery_task_id: ID задачи Celery.
            error_message: текст ошибки.
        """
        job = await self._repo.get_by_celery_id(celery_task_id)
        if not job:
            return
        job.status = JobStatus.FAILED.value
        job.finished_at = datetime.now(UTC)
        job.error_message = error_message[:2000]
        await self._repo.update(job)
        await self._notify(job)


def _format_fetch_result(result: object) -> str:
    """Формирует текст итога парсинга.

    Args:
        result: возврат задачи fetch (FetchResult или list[int] для старых задач).

    Returns:
        str: описание для панели.
    """
    from app.domain.fetch_result import FetchResult

    if isinstance(result, FetchResult):
        return result.summary()
    if isinstance(result, list):
        count = len(result)
        if count == 0:
            return "Новых материалов не найдено"
        return f"Найдено новых материалов: {count}"
    return "Парсинг завершён"


def _format_process_result(result: object) -> str:
    """Формирует текст итога AI-обработки.

    Args:
        result: возврат задачи process.

    Returns:
        str: описание для панели.
    """
    from app.domain.process_result import ProcessResult

    if isinstance(result, ProcessResult):
        return result.summary()
    if isinstance(result, list):
        count = len(result)
        if count == 0:
            return "Посты в очередь модерации не добавлены"
        return f"В очередь модерации: {count} пост(ов)"
    return "Обработка завершена"


async def _on_task_running(celery_task_id: str) -> None:
    """Обработчик старта задачи."""
    from app.infrastructure.database import async_session_factory

    async with async_session_factory() as session:
        await JobTracker(session).mark_running(celery_task_id)
        await session.commit()


async def _on_task_success(celery_task_id: str, task_name: str, result: object) -> None:
    """Обработчик успешного завершения."""
    from app.infrastructure.database import async_session_factory

    summary: str | None = None
    if task_name.endswith("fetch_source"):
        summary = _format_fetch_result(result)
    elif task_name.endswith("process_post"):
        summary = _format_process_result(result)
    elif task_name.endswith("publish_post"):
        summary = "Публикация выполнена"
    elif task_name.endswith("generate_article"):
        if isinstance(result, int):
            summary = f"Статья создана: processed_post #{result}"
        else:
            summary = "Генерация статьи завершена"

    async with async_session_factory() as session:
        await JobTracker(session).mark_success(celery_task_id, summary)
        await session.commit()


async def _on_task_failure(celery_task_id: str, error: str) -> None:
    """Обработчик ошибки задачи."""
    from app.infrastructure.database import async_session_factory

    async with async_session_factory() as session:
        await JobTracker(session).mark_failed(celery_task_id, error)
        await session.commit()


async def report_job_stage(
    celery_task_id: str | None,
    detail: str,
    progress: int,
) -> None:
    """Публикует этап задачи в отдельной транзакции (не блокирует основной сервис).

    Args:
        celery_task_id: ID задачи Celery или None, если учёт отключён.
        detail: описание этапа.
        progress: процент 0–100.
    """
    if not celery_task_id:
        return
    from app.infrastructure.database import async_session_factory

    async with async_session_factory() as session:
        await JobTracker(session).update_stage(celery_task_id, detail, progress)
        await session.commit()


def connect_celery_signals(celery_app: object) -> None:
    """Подключает сигналы Celery к учёту задач.

    Args:
        celery_app: экземпляр Celery (не используется, для явной инициализации).
    """
    from celery.signals import task_failure, task_prerun, task_success

    @task_prerun.connect
    def _prerun_handler(task_id: str | None = None, **_: object) -> None:
        if task_id:
            try:
                run_async(_on_task_running(task_id))
            except Exception as exc:
                logger.warning("Job tracker prerun failed", task_id=task_id, error=str(exc))

    @task_success.connect
    def _success_handler(sender: object | None = None, result: object = None, **_: object) -> None:
        if sender is None:
            return
        task_id = getattr(getattr(sender, "request", None), "id", None)
        task_name = getattr(sender, "name", "") or ""
        if task_id:
            try:
                run_async(_on_task_success(task_id, task_name, result))
            except Exception as exc:
                logger.warning("Job tracker success failed", task_id=task_id, error=str(exc))

    @task_failure.connect
    def _failure_handler(
        task_id: str | None = None,
        exception: BaseException | None = None,
        **_: object,
    ) -> None:
        if task_id:
            try:
                run_async(_on_task_failure(task_id, str(exception) if exception else "Unknown"))
            except Exception as exc:
                logger.warning("Job tracker failure failed", task_id=task_id, error=str(exc))
