"""Репозиторий снимков баланса AI-провайдеров."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.ai_balance_snapshot import AiBalanceSnapshot

# Периодический «сердечный» снимок, даже если баланс не менялся.
_HEARTBEAT = timedelta(hours=6)


class AiBalanceSnapshotRepository:
    """Хранение и выборка истории баланса провайдеров."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def latest(self, provider: str) -> AiBalanceSnapshot | None:
        """Последний снимок баланса провайдера."""
        result = await self._session.execute(
            select(AiBalanceSnapshot)
            .where(AiBalanceSnapshot.provider == provider)
            .order_by(AiBalanceSnapshot.captured_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def record_if_changed(
        self,
        provider: str,
        *,
        currency: str | None,
        total_balance: float | None,
        granted_balance: float | None,
        topped_up_balance: float | None,
    ) -> AiBalanceSnapshot | None:
        """Пишет снимок, если баланс изменился или прошёл heartbeat.

        Args:
            provider: имя провайдера (напр. "deepseek").
            currency: валюта.
            total_balance: суммарный баланс.
            granted_balance: подарочный.
            topped_up_balance: пополненный.

        Returns:
            AiBalanceSnapshot | None: новый снимок или None, если пропущен.
        """
        if total_balance is None:
            return None
        now = datetime.now(UTC)
        last = await self.latest(provider)
        if last is not None:
            same = (
                last.total_balance is not None
                and float(last.total_balance) == float(total_balance)
            )
            captured = last.captured_at
            if captured.tzinfo is None:
                captured = captured.replace(tzinfo=UTC)
            if same and now - captured < _HEARTBEAT:
                return None

        snapshot = AiBalanceSnapshot(
            provider=provider,
            currency=currency,
            total_balance=total_balance,
            granted_balance=granted_balance,
            topped_up_balance=topped_up_balance,
            captured_at=now,
        )
        self._session.add(snapshot)
        await self._session.flush()
        return snapshot

    async def series_since(
        self, provider: str, days: int = 30
    ) -> list[tuple[datetime, float]]:
        """Снимки (время, баланс) за период + одна опорная точка до окна.

        Args:
            provider: имя провайдера.
            days: глубина окна в днях.

        Returns:
            list[tuple[datetime, float]]: точки от старых к новым (UTC).
        """
        since = datetime.now(UTC) - timedelta(days=days)
        rows = (
            (
                await self._session.execute(
                    select(
                        AiBalanceSnapshot.captured_at,
                        AiBalanceSnapshot.total_balance,
                    )
                    .where(
                        AiBalanceSnapshot.provider == provider,
                        AiBalanceSnapshot.captured_at >= since,
                    )
                    .order_by(AiBalanceSnapshot.captured_at)
                )
            )
            .all()
        )
        # Опорная точка непосредственно до окна — чтобы падение на границе
        # окна тоже учлось.
        baseline = (
            await self._session.execute(
                select(
                    AiBalanceSnapshot.captured_at, AiBalanceSnapshot.total_balance
                )
                .where(
                    AiBalanceSnapshot.provider == provider,
                    AiBalanceSnapshot.captured_at < since,
                )
                .order_by(AiBalanceSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()

        series: list[tuple[datetime, float]] = []
        if baseline is not None and baseline[1] is not None:
            ts = baseline[0]
            series.append(
                (ts if ts.tzinfo else ts.replace(tzinfo=UTC), float(baseline[1]))
            )
        for ts, val in rows:
            if val is None:
                continue
            series.append((ts if ts.tzinfo else ts.replace(tzinfo=UTC), float(val)))
        return series
