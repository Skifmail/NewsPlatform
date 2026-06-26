"""Репозиторий снимков статистики каналов."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.channel_stats_snapshot import ChannelStatsSnapshot


class ChannelStatsRepository:
    """CRUD для channel_stats_snapshots."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, snapshot: ChannelStatsSnapshot) -> ChannelStatsSnapshot:
        """Сохраняет снимок статистики.

        Args:
            snapshot: модель снимка.

        Returns:
            ChannelStatsSnapshot: сохранённая запись.
        """
        self._session.add(snapshot)
        await self._session.flush()
        await self._session.refresh(snapshot)
        return snapshot

    async def list_for_channel(
        self,
        channel_id: int,
        *,
        since: datetime | None = None,
        limit: int | None = 90,
    ) -> list[ChannelStatsSnapshot]:
        """История снимков канала (от старых к новым).

        Args:
            channel_id: ID канала.
            since: нижняя граница captured_at (UTC).
            limit: максимум записей; None — без лимита.

        Returns:
            list[ChannelStatsSnapshot]: снимки.
        """
        query = (
            select(ChannelStatsSnapshot)
            .where(ChannelStatsSnapshot.channel_id == channel_id)
            .order_by(ChannelStatsSnapshot.captured_at.desc())
        )
        if since is not None:
            query = query.where(ChannelStatsSnapshot.captured_at >= since)
        if limit is not None:
            query = query.limit(limit)
        result = await self._session.execute(query)
        rows = list(result.scalars().all())
        rows.reverse()
        return rows

    async def latest_for_channel(
        self, channel_id: int
    ) -> ChannelStatsSnapshot | None:
        """Последний снимок канала.

        Args:
            channel_id: ID канала.

        Returns:
            ChannelStatsSnapshot | None: последний снимок.
        """
        result = await self._session.execute(
            select(ChannelStatsSnapshot)
            .where(ChannelStatsSnapshot.channel_id == channel_id)
            .order_by(ChannelStatsSnapshot.captured_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def latest_before(
        self, channel_id: int, before: datetime
    ) -> ChannelStatsSnapshot | None:
        """Снимок непосредственно перед указанным моментом.

        Args:
            channel_id: ID канала.
            before: верхняя граница captured_at.

        Returns:
            ChannelStatsSnapshot | None: предыдущий снимок.
        """
        result = await self._session.execute(
            select(ChannelStatsSnapshot)
            .where(
                ChannelStatsSnapshot.channel_id == channel_id,
                ChannelStatsSnapshot.captured_at < before,
            )
            .order_by(ChannelStatsSnapshot.captured_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def latest_subscribers_snapshot(
        self, channel_id: int
    ) -> ChannelStatsSnapshot | None:
        """Последний снимок с известным числом подписчиков."""
        result = await self._session.execute(
            select(ChannelStatsSnapshot)
            .where(
                ChannelStatsSnapshot.channel_id == channel_id,
                ChannelStatsSnapshot.subscribers.is_not(None),
            )
            .order_by(ChannelStatsSnapshot.captured_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def previous_subscribers_snapshot(
        self, channel_id: int, before: datetime
    ) -> ChannelStatsSnapshot | None:
        """Предыдущий снимок с подписчиками до указанного момента."""
        result = await self._session.execute(
            select(ChannelStatsSnapshot)
            .where(
                ChannelStatsSnapshot.channel_id == channel_id,
                ChannelStatsSnapshot.captured_at < before,
                ChannelStatsSnapshot.subscribers.is_not(None),
            )
            .order_by(ChannelStatsSnapshot.captured_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
