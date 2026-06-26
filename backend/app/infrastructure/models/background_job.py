"""Модель фоновой задачи Celery для панели."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class BackgroundJob(Base):
    """Запись о задаче парсинга, AI или публикации."""

    __tablename__ = "background_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    celery_task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    job_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL"), nullable=True
    )
    raw_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_posts.id", ondelete="SET NULL"), nullable=True
    )
    parent_celery_task_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
