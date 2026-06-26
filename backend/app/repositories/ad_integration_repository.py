"""Репозиторий рекламных интеграций."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.infrastructure.models.ad_integration import AdIntegration


class AdIntegrationRepository:
    """CRUD для ad_integrations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(
        self,
        *,
        channel_id: int | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AdIntegration]:
        """Список рекламных интеграций.

        Args:
            channel_id: фильтр по каналу.
            limit: лимит.
            offset: смещение.

        Returns:
            list[AdIntegration]: интеграции от новых к старым.
        """
        query = (
            select(AdIntegration)
            .options(joinedload(AdIntegration.channel))
            .order_by(AdIntegration.placed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if channel_id is not None:
            query = query.where(AdIntegration.channel_id == channel_id)
        result = await self._session.execute(query)
        return list(result.scalars().unique().all())

    async def get_by_id(self, integration_id: int) -> AdIntegration | None:
        """Интеграция по ID.

        Args:
            integration_id: идентификатор.

        Returns:
            AdIntegration | None: модель.
        """
        return await self._session.get(AdIntegration, integration_id)

    async def create(self, integration: AdIntegration) -> AdIntegration:
        """Создаёт интеграцию.

        Args:
            integration: модель.

        Returns:
            AdIntegration: сохранённая запись.
        """
        self._session.add(integration)
        await self._session.flush()
        await self._session.refresh(integration)
        return integration

    async def update(self, integration: AdIntegration) -> AdIntegration:
        """Обновляет интеграцию.

        Args:
            integration: модель.

        Returns:
            AdIntegration: обновлённая запись.
        """
        await self._session.flush()
        await self._session.refresh(integration)
        return integration

    async def delete(self, integration: AdIntegration) -> None:
        """Удаляет интеграцию.

        Args:
            integration: модель.
        """
        await self._session.delete(integration)

    async def count_for_channel(self, channel_id: int) -> int:
        """Количество рекламных интеграций канала.

        Args:
            channel_id: ID канала.

        Returns:
            int: количество.
        """
        result = await self._session.execute(
            select(func.count(AdIntegration.id)).where(
                AdIntegration.channel_id == channel_id
            )
        )
        return int(result.scalar_one() or 0)

    async def sum_revenue_for_channel(self, channel_id: int) -> float:
        """Сумма цен рекламных интеграций канала.

        Args:
            channel_id: ID канала.

        Returns:
            float: сумма price.
        """
        result = await self._session.execute(
            select(func.coalesce(func.sum(AdIntegration.price), 0)).where(
                AdIntegration.channel_id == channel_id
            )
        )
        return float(result.scalar_one() or 0)
