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
    animate_postcards: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    publish_times: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=(
            "07:00,07:40,08:20,09:00,09:40,10:20,11:00,11:40,12:20,13:00,"
            "13:40,14:20,15:00,15:40,16:20,17:00,17:40,18:20,19:00,19:40,"
            "20:20,21:00,21:40,22:20,23:00"
        ),
    )
    post_footer: Mapped[str | None] = mapped_column(Text, nullable=True)
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
    max_members: Mapped[list["MaxMember"]] = relationship(
        "MaxMember",
        back_populates="channel",
        passive_deletes=True,
    )
    broadcast_stats: Mapped[list["TelegramBroadcastStats"]] = relationship(
        "TelegramBroadcastStats",
        back_populates="channel",
        passive_deletes=True,
    )
