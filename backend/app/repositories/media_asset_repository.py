"""Репозиторий медиатеки (сгенерированные обложки и анимации)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.infrastructure.models.media_asset import MediaAsset


class MediaAssetRepository:
    """CRUD для media_assets."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, asset_id: int) -> MediaAsset | None:
        """Возвращает ассет по ID с каналом."""
        result = await self._session.execute(
            select(MediaAsset)
            .options(joinedload(MediaAsset.channel))
            .where(MediaAsset.id == asset_id)
        )
        return result.scalar_one_or_none()

    async def get_by_storage_url(self, storage_url: str) -> MediaAsset | None:
        """Ищет ассет по storage_url (unique)."""
        result = await self._session.execute(
            select(MediaAsset).where(MediaAsset.storage_url == storage_url)
        )
        return result.scalar_one_or_none()

    async def list_assets(
        self,
        *,
        channel_id: int | None = None,
        kind: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MediaAsset]:
        """Список ассетов от новых к старым, опционально по каналу/типу."""
        query = (
            select(MediaAsset)
            .options(joinedload(MediaAsset.channel))
            .order_by(MediaAsset.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if channel_id is not None:
            query = query.where(MediaAsset.channel_id == channel_id)
        if kind is not None:
            query = query.where(MediaAsset.kind == kind)
        result = await self._session.execute(query)
        return list(result.scalars().unique().all())

    async def create(self, asset: MediaAsset) -> MediaAsset:
        """Создаёт запись медиатеки."""
        self._session.add(asset)
        await self._session.flush()
        await self._session.refresh(asset)
        return asset

    async def delete(self, asset: MediaAsset) -> None:
        """Удаляет запись (файл на диске — отдельно)."""
        await self._session.delete(asset)
        await self._session.flush()
