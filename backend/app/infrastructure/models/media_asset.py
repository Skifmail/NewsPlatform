"""Модель сохранённого медиафайла (обложка / анимация)."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


class MediaAsset(Base):
    """Локальная копия сгенерированного (или сохранённого) медиа.

    Живёт независимо от processed_posts: даже если пост удалён retention'ом
    или ушёл в публикацию без вложения, файл остаётся доступен для скачивания.
    """

    __tablename__ = "media_assets"
    __table_args__ = (
        UniqueConstraint("storage_url", name="uq_media_assets_storage_url"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    processed_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("processed_posts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False, default="cover")
    image_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    storage_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    channel: Mapped["Channel"] = relationship("Channel", back_populates="media_assets")
    processed_post: Mapped["ProcessedPost | None"] = relationship(
        "ProcessedPost",
        back_populates="media_assets",
    )
