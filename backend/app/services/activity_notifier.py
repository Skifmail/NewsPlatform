"""Человекочитаемые события активности для WebSocket."""

from datetime import UTC, datetime

from app.domain.enums import JobStatus, JobType
from app.domain.job_stage import decode_stage
from app.infrastructure.events import publish_event
from app.infrastructure.models.background_job import BackgroundJob

_ESTIMATED_SECONDS: dict[str, int] = {
    JobType.FETCH.value: 40,
    JobType.PROCESS.value: 55,
    JobType.PUBLISH.value: 20,
    JobType.ARTICLE.value: 90,
}

_TYPE_TITLES: dict[str, str] = {
    JobType.FETCH.value: "Парсинг источника",
    JobType.PROCESS.value: "AI-обработка",
    JobType.PUBLISH.value: "Публикация в канал",
    JobType.ARTICLE.value: "Генерация статьи",
}


def detail_for_job(job: BackgroundJob) -> str:
    """Подзаголовок по статусу задачи.

    Args:
        job: запись background_jobs.

    Returns:
        str: текст для UI.
    """
    if job.status == JobStatus.QUEUED.value:
        return "В очереди Celery, ожидание worker…"
    if job.status == JobStatus.RUNNING.value:
        stage_progress, stage_text = decode_stage(job.result_summary)
        if stage_text:
            return stage_text
        if job.job_type == JobType.FETCH.value:
            return "Загрузка новых материалов с источника…"
        if job.job_type == JobType.PROCESS.value:
            return "Рерайт через AI и подготовка постов…"
        if job.job_type == JobType.PUBLISH.value:
            return "Отправка сообщения в канал…"
        if job.job_type == JobType.ARTICLE.value:
            return "Подготовка к генерации статьи…"
        return "Выполняется…"
    if job.status == JobStatus.SUCCESS.value:
        return job.result_summary or "Успешно завершено"
    if job.status == JobStatus.FAILED.value:
        return job.error_message or "Ошибка выполнения"
    return job.label


def progress_for_job(job: BackgroundJob) -> int:
    """Оценка прогресса 0–100 по статусу и времени.

    Args:
        job: запись background_jobs.

    Returns:
        int: процент для прогресс-бара.
    """
    if job.status == JobStatus.QUEUED.value:
        return 12
    if job.status == JobStatus.SUCCESS.value:
        return 100
    if job.status == JobStatus.FAILED.value:
        return 100
    if job.status == JobStatus.RUNNING.value:
        stage_progress, _ = decode_stage(job.result_summary)
        if stage_progress is not None:
            return stage_progress
        base = 22
        if job.started_at:
            elapsed = (datetime.now(UTC) - job.started_at).total_seconds()
            est = _ESTIMATED_SECONDS.get(job.job_type, 45)
            return min(92, base + int((elapsed / est) * 70))
        return 38
    return 5


def phase_for_status(status: str) -> str:
    """Фаза для фронтенда.

    Args:
        status: статус задачи.

    Returns:
        str: queued | running | done | error.
    """
    if status == JobStatus.FAILED.value:
        return "error"
    if status == JobStatus.SUCCESS.value:
        return "done"
    if status == JobStatus.RUNNING.value:
        return "running"
    return "queued"


async def notify_job(job: BackgroundJob) -> None:
    """Публикует обновление фоновой задачи.

    Args:
        job: актуальная запись background_jobs.
    """
    title = job.label if job.label else _TYPE_TITLES.get(job.job_type, "Задача")
    payload: dict[str, object] = {
        "id": f"job-{job.id}",
        "kind": "job",
        "job_id": job.id,
        "job_type": job.job_type,
        "phase": phase_for_status(job.status),
        "title": title,
        "detail": detail_for_job(job),
        "progress": progress_for_job(job),
        "status": job.status,
    }
    if job.raw_post_id is not None:
        payload["raw_post_id"] = job.raw_post_id
    await publish_event("activity", payload)


async def notify_simple(
    activity_id: str,
    *,
    kind: str,
    phase: str,
    title: str,
    detail: str,
    progress: int = 100,
    raw_post_id: int | None = None,
) -> None:
    """Публикует разовое событие (пост, публикация и т.д.).

    Args:
        activity_id: уникальный ключ для UI.
        kind: категория (post, publish, system).
        phase: queued | running | done | error.
        title: заголовок.
        detail: подзаголовок.
        progress: процент 0–100.
        raw_post_id: ID сырого поста для связи с задачей AI.
    """
    payload: dict[str, object] = {
        "id": activity_id,
        "kind": kind,
        "phase": phase,
        "title": title,
        "detail": detail,
        "progress": progress,
    }
    if raw_post_id is not None:
        payload["raw_post_id"] = raw_post_id
    await publish_event("activity", payload)
