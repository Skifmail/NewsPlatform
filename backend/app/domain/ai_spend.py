"""Расчёт расходов провайдера из истории снимков баланса.

Провайдер отдаёт только текущий баланс. Расход за период = сумма ПАДЕНИЙ
баланса между соседними снимками, пополнение = сумма РОСТА. Так из простых
снимков получаем историю трат.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class SpendSummary:
    """Сводка расходов провайдера по окнам."""

    spent_24h: float = 0.0
    spent_7d: float = 0.0
    spent_30d: float = 0.0
    topped_up_30d: float = 0.0
    points: list[tuple[str, float]] = field(default_factory=list)


def _spent_since(
    series: list[tuple[datetime, float]], since: datetime
) -> float:
    """Сумма падений баланса среди пар, где поздняя точка не раньше ``since``."""
    total = 0.0
    for (_, prev_val), (curr_time, curr_val) in zip(series, series[1:]):
        if curr_time >= since:
            delta = curr_val - prev_val
            if delta < 0:
                total += -delta
    return round(total, 8)


def _topped_since(
    series: list[tuple[datetime, float]], since: datetime
) -> float:
    """Сумма ростов баланса среди пар, где поздняя точка не раньше ``since``."""
    total = 0.0
    for (_, prev_val), (curr_time, curr_val) in zip(series, series[1:]):
        if curr_time >= since:
            delta = curr_val - prev_val
            if delta > 0:
                total += delta
    return round(total, 8)


def compute_spend(
    series: list[tuple[datetime, float]],
    now: datetime,
    *,
    max_points: int = 60,
) -> SpendSummary:
    """Считает расходы за 24ч/7д/30д и пополнение за 30д.

    Args:
        series: снимки (время, баланс) от СТАРЫХ к НОВЫМ.
        now: текущий момент (UTC).
        max_points: сколько последних точек вернуть для графика.

    Returns:
        SpendSummary: расходы по окнам и точки для графика.
    """
    clean = [(t, float(v)) for t, v in series if v is not None]
    if len(clean) < 2:
        pts = [(t.isoformat(), float(v)) for t, v in clean]
        return SpendSummary(points=pts)

    day = now - timedelta(days=1)
    week = now - timedelta(days=7)
    month = now - timedelta(days=30)
    points = [(t.isoformat(), round(v, 8)) for t, v in clean[-max_points:]]
    return SpendSummary(
        spent_24h=_spent_since(clean, day),
        spent_7d=_spent_since(clean, week),
        spent_30d=_spent_since(clean, month),
        topped_up_30d=_topped_since(clean, month),
        points=points,
    )
