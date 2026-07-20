"""Снимок нативной статистики Telegram-канала (stats.getBroadcastStats)."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class TelegramBroadcastStats(Base):
    """Скалярные показатели статистики канала на момент замера.

    Наполняется только для каналов, у которых Telegram включил статистику
    (достаточно крупных) и при user-аккаунте-администраторе. Хранит историю
    замеров для построения динамики.
    """

    __tablename__ = "telegram_broadcast_stats"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    followers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    followers_prev: Mapped[int | None] = mapped_column(Integer, nullable=True)
    views_per_post: Mapped[float | None] = mapped_column(Float, nullable=True)
    views_per_post_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_per_post: Mapped[float | None] = mapped_column(Float, nullable=True)
    shares_per_post_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    reactions_per_post: Mapped[float | None] = mapped_column(Float, nullable=True)
    reactions_per_post_prev: Mapped[float | None] = mapped_column(Float, nullable=True)
    enabled_notifications_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    period_min: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    period_max: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    channel: Mapped["Channel"] = relationship(
        "Channel", back_populates="broadcast_stats"
    )
