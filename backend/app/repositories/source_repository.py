"""Репозиторий источников."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.source import Source


class SourceRepository:
    """CRUD для таблицы sources."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Source]:
        """Список всех источников.

        Returns:
            list[Source]: источники.
        """
        result = await self._session.execute(
            select(Source).order_by(Source.id)
        )
        return list(result.scalars().all())

    async def list_active(self) -> list[Source]:
        """Активные источники.

        Returns:
            list[Source]: активные источники.
        """
        result = await self._session.execute(
            select(Source).where(Source.is_active.is_(True))
        )
        return list(result.scalars().all())

    async def get_by_id(self, source_id: int) -> Source | None:
        """Источник по ID.

        Args:
            source_id: идентификатор.

        Returns:
            Source | None: модель или None.
        """
        return await self._session.get(Source, source_id)

    async def create(self, source: Source) -> Source:
        """Создаёт источник.

        Args:
            source: модель.

        Returns:
            Source: сохранённая модель.
        """
        self._session.add(source)
        await self._session.flush()
        await self._session.refresh(source)
        return source

    async def update(self, source: Source) -> Source:
        """Обновляет источник.

        Args:
            source: модель.

        Returns:
            Source: обновлённая модель.
        """
        await self._session.flush()
        await self._session.refresh(source)
        return source

    async def delete(self, source: Source) -> None:
        """Удаляет источник.

        Args:
            source: модель.
        """
        await self._session.delete(source)

    async def mark_fetched(self, source_id: int) -> None:
        """Обновляет last_fetched_at.

        Args:
            source_id: ID источника.
        """
        source = await self.get_by_id(source_id)
        if source:
            source.last_fetched_at = datetime.now(UTC)
            await self._session.flush()
