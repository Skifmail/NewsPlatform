"""Модель обработанного AI поста."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class ProcessedPost(Base):
    """Пост в очереди модерации или опубликованный."""

    __tablename__ = "processed_posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    raw_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("raw_posts.id", ondelete="CASCADE"), nullable=True
    )
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False
    )
    rewritten_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_mode: Mapped[str] = mapped_column(String(32), default="news")
    article_title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    article_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    telegraph_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    research_sources: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    publish_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    raw_post: Mapped["RawPost"] = relationship("RawPost", back_populates="processed_posts")
    channel: Mapped["Channel"] = relationship("Channel", back_populates="processed_posts")
    publish_logs: Mapped[list["PublishLog"]] = relationship(
        "PublishLog", back_populates="processed_post"
    )
