"""Репозиторий логов ошибок приложения (для панели диагностики)."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.app_error_log import AppErrorLog


class AppErrorLogRepository:
    """Чтение и обслуживание таблицы app_error_logs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_recent(
        self,
        *,
        limit: int = 100,
        level: str | None = None,
        since_hours: int | None = None,
    ) -> list[AppErrorLog]:
        """Последние записи, опционально с фильтром по уровню и времени.

        Args:
            limit: максимум записей (1..500).
            level: точный уровень (ERROR/WARNING/CRITICAL) либо None — все.
            since_hours: только записи за последние N часов, либо None.

        Returns:
            list[AppErrorLog]: записи, новые сверху.
        """
        stmt = select(AppErrorLog).order_by(AppErrorLog.created_at.desc())
        if level:
            stmt = stmt.where(AppErrorLog.level == level.upper())
        if since_hours:
            cutoff = datetime.now(UTC) - timedelta(hours=since_hours)
            stmt = stmt.where(AppErrorLog.created_at >= cutoff)
        stmt = stmt.limit(max(1, min(limit, 500)))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def count_since(self, hours: int) -> int:
        """Число записей за последние N часов.

        Args:
            hours: окно в часах.

        Returns:
            int: количество ошибок.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        result = await self._session.execute(
            select(func.count(AppErrorLog.id)).where(
                AppErrorLog.created_at >= cutoff
            )
        )
        return int(result.scalar_one())

    async def purge_older_than(self, days: int) -> int:
        """Удаляет записи старше N дней.

        Args:
            days: срок хранения.

        Returns:
            int: сколько строк удалено.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            delete(AppErrorLog).where(AppErrorLog.created_at < cutoff)
        )
        return int(result.rowcount or 0)
