"""Метрики отдельного поста на платформе."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class PostMetric(Base):
    """Просмотры, реакции и охват поста на соцплатформе."""

    __tablename__ = "post_metrics"
    __table_args__ = (
        UniqueConstraint("channel_id", "platform_post_id", name="uq_post_metrics_channel_post"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    processed_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("processed_posts.id", ondelete="SET NULL"), nullable=True
    )
    publish_log_id: Mapped[int | None] = mapped_column(
        ForeignKey("publish_log.id", ondelete="SET NULL"), nullable=True
    )
    platform_post_id: Mapped[str] = mapped_column(String(255), nullable=False)
    post_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    views: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forwards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reactions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    comments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reach: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    channel: Mapped["Channel"] = relationship("Channel", back_populates="post_metrics")
    processed_post: Mapped["ProcessedPost | None"] = relationship("ProcessedPost")
    publish_log: Mapped["PublishLog | None"] = relationship("PublishLog")
