"""Хранение дополнительных материалов вне общей очереди автопубликации."""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.supplements import DEFAULT_RULES, FACT_RULES, NEWS_RULES
from app.infrastructure.database import Base


class SupplementConfig(Base):
    """Настройки дополнительной рубрики и привязка редактора.

    Attributes:
        channel_id: Канал-владелец настройки.
        enabled: Разрешение подготовки, не автоматической публикации.
        recipient_id: Подтверждённый через одноразовую ссылку пользователь MAX.
        pair_hash: Хеш одноразового токена, не сам токен.
    """

    __tablename__ = "supplement_configs"
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    clock: Mapped[str] = mapped_column(String(5), default="18:00")
    fact_days: Mapped[list[int]] = mapped_column(JSON, default=lambda: [0, 4])
    news_day: Mapped[int] = mapped_column(default=2)
    rules: Mapped[str] = mapped_column(Text, default=DEFAULT_RULES)
    fact_rules: Mapped[str] = mapped_column(Text, default=FACT_RULES)
    news_rules: Mapped[str] = mapped_column(Text, default=NEWS_RULES)
    recipient_id: Mapped[int | None] = mapped_column(BigInteger)
    recipient_name: Mapped[str | None] = mapped_column(String(255))
    pair_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    pair_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SupplementDraft(Base):
    """Версионируемый черновик, журнал исследования и результат согласования.

    Attributes:
        slot_key: Уникальный слот канала, защищающий от двойной генерации.
        revision: Версия, включаемая в кнопки согласования.
        trace: Снимок правил, поиска, объяснения модели и проверок.
        status: Состояние подготовки, согласования или доставки.
        progress_stage: Текущий наблюдаемый этап фоновой работы.
        progress_percent: Оценка завершённости этапов от 0 до 100.
        progress_detail: Понятное пользователю описание текущей операции.
        progress_updated_at: Время последнего подтверждённого продвижения.
        target_chat_id: Адрес канала, зафиксированный перед показом редактору.
        image_url: Сохранённая обложка показанной версии.
    """

    __tablename__ = "supplement_drafts"
    __table_args__ = (
        UniqueConstraint("channel_id", "slot_key", name="uq_supplement_slot"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(
        ForeignKey("channels.id", ondelete="CASCADE"), index=True
    )
    slot_key: Mapped[str] = mapped_column(String(80))
    requested_kind: Mapped[str] = mapped_column(String(10))
    kind: Mapped[str] = mapped_column(String(10), default="fact")
    title: Mapped[str] = mapped_column(String(255), default="")
    text: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str | None] = mapped_column(Text)
    image_source: Mapped[str | None] = mapped_column(String(50))
    image_prompt: Mapped[str | None] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    trace: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress_stage: Mapped[str] = mapped_column(String(40), default="queued")
    progress_percent: Mapped[int] = mapped_column(default=5)
    progress_detail: Mapped[str] = mapped_column(
        String(255), default="Задание ожидает запуска"
    )
    progress_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revision: Mapped[int] = mapped_column(default=1)
    review_mid: Mapped[str | None] = mapped_column(String(255))
    target_chat_id: Mapped[str] = mapped_column(String(255), default="")
    error: Mapped[str | None] = mapped_column(Text)
    decided_by: Mapped[int | None] = mapped_column(BigInteger)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    platform_mid: Mapped[str | None] = mapped_column(String(255))
    platform_url: Mapped[str | None] = mapped_column(Text)
    processed_post_id: Mapped[int | None] = mapped_column(
        ForeignKey("processed_posts.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
