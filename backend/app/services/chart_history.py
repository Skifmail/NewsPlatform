"""Агрегация точек графиков аналитики по периодам.

Подписчики — stock-метрика: в каждой корзине показываем уровень на конец интервала.
Просмотры — flow-метрика: в корзине суммируем прирост ``total_views`` между соседними
снимками (не накопительный итог по каналу).

Сравнение с прошлым периодом: today↔вчера, week↔прошлая неделя, month↔прошлые 30 дней,
all — последний полный месяц ↔ предыдущий.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

from app.infrastructure.models.channel_stats_snapshot import ChannelStatsSnapshot

GrowthMetric = Literal["subscribers", "views"]
GrowthGranularity = Literal["30min", "day", "month"]

PREVIOUS_PERIOD_LABELS = {
    "today": "вчера",
    "week": "прошлая неделя",
    "month": "прошлые 30 дней",
    "all": "предыдущий месяц",
}


@dataclass(frozen=True)
class PeriodBounds:
    """Границы текущего и предыдущего периода для сравнения."""

    start: datetime
    end: datetime
    previous_start: datetime
    previous_end: datetime
    granularity: GrowthGranularity


@dataclass(frozen=True)
class ChartHistoryResult:
    """Готовая серия для графика и сравнение с прошлым периодом."""

    period: str
    metric: GrowthMetric
    granularity: GrowthGranularity
    points: list[tuple[str, int | None]]
    period_total: int | None
    period_delta: int | None
    period_delta_percent: float | None
    previous_period_label: str | None
    subscribers_unsubscribed: int | None = None


def period_bounds(period: str, now: datetime | None = None) -> PeriodBounds:
    """Возвращает границы периода и шаг агрегации.

    Args:
        period: today | week | month | all.
        now: опорное время (UTC); для тестов.

    Returns:
        PeriodBounds: интервалы и granularity.
    """
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)

    today_start = current.replace(hour=0, minute=0, second=0, microsecond=0)

    if period == "today":
        return PeriodBounds(
            start=today_start,
            end=current,
            previous_start=today_start - timedelta(days=1),
            previous_end=today_start,
            granularity="30min",
        )
    if period == "week":
        start = current - timedelta(days=7)
        return PeriodBounds(
            start=start,
            end=current,
            previous_start=start - timedelta(days=7),
            previous_end=start,
            granularity="day",
        )
    if period == "month":
        start = current - timedelta(days=30)
        return PeriodBounds(
            start=start,
            end=current,
            previous_start=start - timedelta(days=30),
            previous_end=start,
            granularity="day",
        )

    # all — по месяцам; сравниваем последний полный месяц с предыдущим
    month_start = current.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    prev_month_end = month_start
    prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
    return PeriodBounds(
        start=datetime(1970, 1, 1, tzinfo=UTC),
        end=current,
        previous_start=prev_month_start,
        previous_end=prev_month_end,
        granularity="month",
    )


def bucket_start(dt: datetime, granularity: GrowthGranularity) -> datetime:
    """Округляет момент времени до начала корзины."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    if granularity == "30min":
        minute = (dt.minute // 30) * 30
        return dt.replace(minute=minute, second=0, microsecond=0)
    if granularity == "day":
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def iter_bucket_starts(
    start: datetime,
    end: datetime,
    granularity: GrowthGranularity,
) -> list[datetime]:
    """Генерирует непрерывную шкалу корзин от start до end включительно."""
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)

    cursor = bucket_start(start, granularity)
    end_bucket = bucket_start(end, granularity)
    buckets: list[datetime] = []

    while cursor <= end_bucket:
        buckets.append(cursor)
        if granularity == "30min":
            cursor += timedelta(minutes=30)
        elif granularity == "day":
            cursor += timedelta(days=1)
        else:
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)

    return buckets


def _view_increments(
    snapshots: list[ChannelStatsSnapshot],
) -> list[tuple[datetime, int]]:
    """Прирост просмотров между соседними снимками (только неотрицательный)."""
    increments: list[tuple[datetime, int]] = []
    for index in range(1, len(snapshots)):
        previous = snapshots[index - 1].total_views
        current = snapshots[index].total_views
        if previous is None or current is None:
            continue
        delta = current - previous
        if delta > 0:
            increments.append((snapshots[index].captured_at, delta))
    return increments


def _sum_increments_in_window(
    snapshots: list[ChannelStatsSnapshot],
    window_start: datetime,
    window_end: datetime,
) -> int | None:
    """Сумма приростов просмотров в полуинтервале [start, end)."""
    increments = _view_increments(snapshots)
    total = 0
    has_data = False
    for captured_at, delta in increments:
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        if window_start <= captured_at < window_end:
            total += delta
            has_data = True
    return total if has_data else None


def _aggregate_views_buckets(
    snapshots: list[ChannelStatsSnapshot],
    bounds: PeriodBounds,
) -> dict[datetime, int]:
    """Суммирует приросты просмотров по корзинам периода."""
    buckets: dict[datetime, int] = {}
    for captured_at, delta in _view_increments(snapshots):
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        if captured_at < bounds.start or captured_at > bounds.end:
            continue
        key = bucket_start(captured_at, bounds.granularity)
        buckets[key] = buckets.get(key, 0) + delta
    return buckets


def _aggregate_subscribers_buckets(
    snapshots: list[ChannelStatsSnapshot],
    bounds: PeriodBounds,
) -> dict[datetime, int]:
    """Берёт последний уровень подписчиков в каждой корзине."""
    buckets: dict[datetime, int] = {}
    latest_time: dict[datetime, datetime] = {}
    for snapshot in snapshots:
        captured_at = snapshot.captured_at
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        if captured_at < bounds.start or captured_at > bounds.end:
            continue
        if snapshot.subscribers is None:
            continue
        key = bucket_start(captured_at, bounds.granularity)
        prev_time = latest_time.get(key)
        if prev_time is None or captured_at >= prev_time:
            buckets[key] = snapshot.subscribers
            latest_time[key] = captured_at
    return buckets


def _fill_subscriber_series(
    bucket_keys: list[datetime],
    values: dict[datetime, int],
) -> list[tuple[str, int | None]]:
    """Заполняет пропуски carry-forward последнего известного уровня."""
    points: list[tuple[str, int | None]] = []
    last_known: int | None = None
    for key in bucket_keys:
        if key in values:
            last_known = values[key]
        points.append((key.isoformat(), last_known))
    return points


def _fill_views_series(
    bucket_keys: list[datetime],
    values: dict[datetime, int],
) -> list[tuple[str, int | None]]:
    """Просмотры: пустые корзины = 0 (явный ноль на графике)."""
    return [
        (key.isoformat(), values.get(key, 0))
        for key in bucket_keys
    ]


def _period_total_views(
    snapshots: list[ChannelStatsSnapshot],
    window_start: datetime,
    window_end: datetime,
) -> int | None:
    """Итого просмотров, набранных в окне [start, end)."""
    return _sum_increments_in_window(snapshots, window_start, window_end)


def _period_end_subscribers(
    snapshots: list[ChannelStatsSnapshot],
    window_start: datetime,
    window_end: datetime,
) -> int | None:
    """Подписчики на конец окна — последний снимок в [start, end)."""
    in_window = [
        s
        for s in snapshots
        if window_start
        <= (s.captured_at if s.captured_at.tzinfo else s.captured_at.replace(tzinfo=UTC))
        < window_end
        and s.subscribers is not None
    ]
    if not in_window:
        return None
    return in_window[-1].subscribers


def _delta_percent(current: int | None, previous: int | None) -> float | None:
    if current is None or previous is None:
        return None
    if previous == 0:
        return 100.0 if current > 0 else 0.0
    return round((current - previous) / previous * 100, 1)


def sum_unsubscribes_in_window(
    snapshots: list[ChannelStatsSnapshot],
    window_start: datetime,
    window_end: datetime,
) -> int | None:
    """Отписки (падения счётчика) только внутри окна."""
    in_window = [
        s
        for s in snapshots
        if window_start
        <= (s.captured_at if s.captured_at.tzinfo else s.captured_at.replace(tzinfo=UTC))
        < window_end
    ]
    if not in_window:
        return None
    total = 0
    has_value = False
    for index in range(1, len(in_window)):
        prev_sub = in_window[index - 1].subscribers
        curr_sub = in_window[index].subscribers
        if prev_sub is None or curr_sub is None:
            continue
        has_value = True
        if curr_sub < prev_sub:
            total += prev_sub - curr_sub
    if not has_value:
        return None
    return total if len(in_window) > 1 else 0


def build_chart_history(
    period: str,
    metric: GrowthMetric,
    snapshots: list[ChannelStatsSnapshot],
    *,
    now: datetime | None = None,
) -> ChartHistoryResult:
    """Строит серию графика и сравнение с прошлым периодом.

    Args:
        period: today | week | month | all.
        metric: subscribers | views.
        snapshots: все релевантные снимки (включая baseline до периода), по возрастанию.
        now: опорное время UTC.

    Returns:
        ChartHistoryResult: точки, итог периода и дельта к прошлому периоду.
    """
    bounds = period_bounds(period, now)
    bucket_keys = iter_bucket_starts(bounds.start, bounds.end, bounds.granularity)

    if metric == "views":
        raw = _aggregate_views_buckets(snapshots, bounds)
        points = _fill_views_series(bucket_keys, raw)
        # убираем ведущие нулевые корзины для читаемости (кроме today)
        if period != "today":
            while len(points) > 2 and points[0][1] == 0:
                points.pop(0)
        period_total = _period_total_views(snapshots, bounds.start, bounds.end)
        prev_total = _period_total_views(
            snapshots, bounds.previous_start, bounds.previous_end
        )
    else:
        raw = _aggregate_subscribers_buckets(snapshots, bounds)
        points = _fill_subscriber_series(bucket_keys, raw)
        # убираем ведущие пустые точки
        while points and points[0][1] is None:
            points.pop(0)
        period_total = _period_end_subscribers(snapshots, bounds.start, bounds.end)
        prev_total = _period_end_subscribers(
            snapshots, bounds.previous_start, bounds.previous_end
        )

    period_delta = None
    if period_total is not None and prev_total is not None:
        period_delta = period_total - prev_total

    unsubscribed = None
    if metric == "subscribers":
        unsubscribed = sum_unsubscribes_in_window(
            snapshots, bounds.start, bounds.end
        )

    return ChartHistoryResult(
        period=period,
        metric=metric,
        granularity=bounds.granularity,
        points=points,
        period_total=period_total,
        period_delta=period_delta,
        period_delta_percent=_delta_percent(period_total, prev_total),
        previous_period_label=PREVIOUS_PERIOD_LABELS.get(period),
        subscribers_unsubscribed=unsubscribed,
    )
