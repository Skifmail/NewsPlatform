"""Модель участника MAX-канала.

MAX Bot API (эндпоинт ``GET /chats/{id}/members``) отдаёт полный список
участников с временем вступления и активности. Храним всё, что отдаёт API,
плюс служебные поля для детекции роста и отписок между синхронизациями.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class MaxMember(Base):
    """Участник MAX-канала со всей доступной от API информацией."""

    __tablename__ = "max_members"
    __table_args__ = (
        UniqueConstraint("channel_id", "user_id", name="uq_max_members_channel_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Профиль (то, что отдаёт API)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Роли и права
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    permissions: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Временные метки от API
    join_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    last_access_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Служебные: присутствие и детекция отписок между синхронизациями
    is_present: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False, index=True
    )
    left_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    channel: Mapped["Channel"] = relationship("Channel", back_populates="max_members")
