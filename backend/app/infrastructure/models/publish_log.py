"""Модель лога публикаций."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class PublishLog(Base):
    """Запись о попытке публикации."""

    __tablename__ = "publish_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    processed_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("processed_posts.id", ondelete="SET NULL"), nullable=True
    )
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("channels.id", ondelete="SET NULL"), nullable=True
    )
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    processed_post: Mapped["ProcessedPost | None"] = relationship(
        "ProcessedPost", back_populates="publish_logs"
    )
