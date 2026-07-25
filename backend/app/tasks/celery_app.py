"""Celery application."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "content_platform",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.fetch_tasks",
        "app.tasks.ai_tasks",
        "app.tasks.publish_tasks",
        "app.tasks.retention_tasks",
        "app.tasks.scheduler_tasks",
        "app.tasks.article_tasks",
        "app.tasks.analytics_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,
    worker_cancel_long_running_tasks_on_connection_loss=True,
    task_default_retry_delay=60,
    task_max_retries=5,
    beat_schedule={
        "platform-scheduler-tick": {
            "task": "app.tasks.scheduler_tasks.platform_scheduler_tick",
            "schedule": crontab(minute="*"),
        },
    },
)

# Статусы задач обновляются в теле задач (job_execution), не через signals:
# run_async в signal-handler конфликтует с loop prefork worker.

# Воркер/бит не вызывают setup_logging (loguru работает на дефолтном sink),
# поэтому регистрируем БД-sink ошибок здесь — иначе ошибки конвейера,
# которые происходят именно в воркере, не попадут в окно диагностики.
from app.infrastructure.error_log_sink import register_db_error_sink  # noqa: E402

register_db_error_sink()
