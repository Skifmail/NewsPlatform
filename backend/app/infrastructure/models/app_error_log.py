"""Модель записи об ошибке приложения (для окна логов в панели)."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class AppErrorLog(Base):
    """Единая запись ошибки/предупреждения из любого процесса (backend, worker)."""

    __tablename__ = "app_error_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    # ERROR | CRITICAL | WARNING
    level: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    # backend | worker | beat
    service: Mapped[str] = mapped_column(String(32), nullable=False, default="app")
    # module:function:line
    source: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    message: Mapped[str] = mapped_column(Text, nullable=False)
    # Трейсбек / доп. контекст (может быть пустым)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)
