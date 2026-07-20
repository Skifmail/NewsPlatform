"""Снимок баланса AI-провайдера для истории расходов.

Провайдеры (DeepSeek) отдают только ТЕКУЩИЙ баланс, без истории трат.
Поэтому периодически снимаем баланс, а расход считаем как падение между
снимками (рост = пополнение).
"""

from datetime import datetime

from sqlalchemy import DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class AiBalanceSnapshot(Base):
    """Точка баланса провайдера во времени."""

    __tablename__ = "ai_balance_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    total_balance: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    granted_balance: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    topped_up_balance: Mapped[float | None] = mapped_column(
        Numeric(20, 8), nullable=True
    )
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
