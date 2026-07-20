"""Репозиторий снимков нативной статистики Telegram-каналов."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.telegram_broadcast_stats import TelegramBroadcastStats
from app.infrastructure.stats.base import BroadcastStatsDTO


class TelegramBroadcastStatsRepository:
    """Хранение и выборка снимков stats.getBroadcastStats."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_snapshot(
        self, channel_id: int, dto: BroadcastStatsDTO
    ) -> TelegramBroadcastStats:
        """Сохраняет новый снимок статистики канала.

        Args:
            channel_id: ID канала.
            dto: показатели статистики.

        Returns:
            TelegramBroadcastStats: сохранённая запись.
        """
        row = TelegramBroadcastStats(
            channel_id=channel_id,
            followers=int(dto.followers) if dto.followers is not None else None,
            followers_prev=(
                int(dto.followers_prev) if dto.followers_prev is not None else None
            ),
            views_per_post=dto.views_per_post,
            views_per_post_prev=dto.views_per_post_prev,
            shares_per_post=dto.shares_per_post,
            shares_per_post_prev=dto.shares_per_post_prev,
            reactions_per_post=dto.reactions_per_post,
            reactions_per_post_prev=dto.reactions_per_post_prev,
            enabled_notifications_pct=dto.enabled_notifications_pct,
            period_min=dto.period_min,
            period_max=dto.period_max,
            collected_at=datetime.now(UTC),
        )
        self._session.add(row)
        await self._session.flush()
        return row

    async def latest_for_channel(
        self, channel_id: int
    ) -> TelegramBroadcastStats | None:
        """Возвращает последний снимок статистики канала."""
        result = await self._session.execute(
            select(TelegramBroadcastStats)
            .where(TelegramBroadcastStats.channel_id == channel_id)
            .order_by(TelegramBroadcastStats.collected_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
