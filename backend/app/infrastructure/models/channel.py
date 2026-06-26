"""Модель канала публикации."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class Channel(Base):
    """Канал Telegram / VK / MAX."""

    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    platform_id: Mapped[str] = mapped_column(String(255), nullable=False)
    topic: Mapped[str] = mapped_column(String(50), nullable=False)
    style_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_prompt_guidelines: Mapped[str | None] = mapped_column(Text, nullable=True)
    cross_promote_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    cross_promote_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cross_promote_emoji_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    content_mode: Mapped[str] = mapped_column(String(32), default="news")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    publish_interval_minutes: Mapped[int] = mapped_column(default=60)
    publish_window_start: Mapped[str] = mapped_column(String(5), default="08:00")
    publish_window_end: Mapped[str] = mapped_column(String(5), default="22:00")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    processed_posts: Mapped[list["ProcessedPost"]] = relationship(
        "ProcessedPost",
        back_populates="channel",
        passive_deletes=True,
    )
    stats_snapshots: Mapped[list["ChannelStatsSnapshot"]] = relationship(
        "ChannelStatsSnapshot",
        back_populates="channel",
        passive_deletes=True,
    )
    post_metrics: Mapped[list["PostMetric"]] = relationship(
        "PostMetric",
        back_populates="channel",
        passive_deletes=True,
    )
    ad_integrations: Mapped[list["AdIntegration"]] = relationship(
        "AdIntegration",
        back_populates="channel",
        passive_deletes=True,
    )
