"""Тесты агрегации графиков аналитики."""

from datetime import UTC, datetime, timedelta

from app.infrastructure.models.channel_stats_snapshot import ChannelStatsSnapshot
from app.services.chart_history import (
    build_chart_history,
    period_bounds,
    period_view_windows,
)


def _snap(
    *,
    at: datetime,
    subscribers: int | None = None,
    total_views: int | None = None,
) -> ChannelStatsSnapshot:
    return ChannelStatsSnapshot(
        channel_id=1,
        subscribers=subscribers,
        total_views=total_views,
        captured_at=at,
    )


def test_views_today_buckets_30min() -> None:
    """Просмотры за сегодня — прирост по 30-минутным корзинам, не накопительный итог."""
    now = datetime(2026, 6, 25, 17, 30, tzinfo=UTC)
    snapshots = [
        _snap(at=datetime(2026, 6, 25, 9, 0, tzinfo=UTC), total_views=1000),
        _snap(at=datetime(2026, 6, 25, 10, 27, tzinfo=UTC), total_views=1010),
        _snap(at=datetime(2026, 6, 25, 12, 6, tzinfo=UTC), total_views=1025),
        _snap(at=datetime(2026, 6, 25, 15, 40, tzinfo=UTC), total_views=1040),
        _snap(at=datetime(2026, 6, 25, 17, 11, tzinfo=UTC), total_views=1060),
    ]
    result = build_chart_history("today", "views", snapshots, now=now)

    assert result.granularity == "30min"
    assert result.period_total == 60
    values = [p[1] for p in result.points if p[1]]
    assert sum(values) == 60
    assert max(values) < 200


def test_views_week_daily_buckets() -> None:
    """За неделю — столбцы по дням, итог = сумма приростов."""
    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    snapshots = [
        _snap(at=datetime(2026, 6, 18, 10, 0, tzinfo=UTC), total_views=500),
        _snap(at=datetime(2026, 6, 19, 10, 0, tzinfo=UTC), total_views=520),
        _snap(at=datetime(2026, 6, 20, 10, 0, tzinfo=UTC), total_views=530),
        _snap(at=datetime(2026, 6, 25, 10, 0, tzinfo=UTC), total_views=600),
    ]
    result = build_chart_history("week", "views", snapshots, now=now)

    assert result.granularity == "day"
    assert result.period_total == 100


def test_views_period_delta_vs_previous() -> None:
    """Дельта просмотров сравнивается с прошлым периодом."""
    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    snapshots = [
        # прошлая неделя: +30
        _snap(at=datetime(2026, 6, 11, 10, 0, tzinfo=UTC), total_views=100),
        _snap(at=datetime(2026, 6, 17, 10, 0, tzinfo=UTC), total_views=130),
        # текущая неделя: +70
        _snap(at=datetime(2026, 6, 18, 10, 0, tzinfo=UTC), total_views=130),
        _snap(at=datetime(2026, 6, 25, 10, 0, tzinfo=UTC), total_views=200),
    ]
    result = build_chart_history("week", "views", snapshots, now=now)

    assert result.period_total == 70
    assert result.period_delta == 40
    assert result.previous_period_label == "прошлая неделя"


def test_subscribers_stock_per_day() -> None:
    """Подписчики — уровень на конец дня, не прирост."""
    now = datetime(2026, 6, 25, 12, 0, tzinfo=UTC)
    snapshots = [
        _snap(at=datetime(2026, 6, 23, 10, 0, tzinfo=UTC), subscribers=100),
        _snap(at=datetime(2026, 6, 23, 18, 0, tzinfo=UTC), subscribers=105),
        _snap(at=datetime(2026, 6, 24, 10, 0, tzinfo=UTC), subscribers=110),
    ]
    result = build_chart_history("week", "subscribers", snapshots, now=now)

    assert result.period_total == 110
    day_values = {p[0][:10]: p[1] for p in result.points if p[1] is not None}
    assert day_values.get("2026-06-23") == 105
    assert day_values.get("2026-06-24") == 110


def test_period_bounds_today() -> None:
    """Границы today — с полуночи."""
    now = datetime(2026, 6, 25, 15, 0, tzinfo=UTC)
    bounds = period_bounds("today", now)
    assert bounds.granularity == "30min"
    assert bounds.start == datetime(2026, 6, 25, 0, 0, tzinfo=UTC)


def test_period_view_windows_rolling_hours() -> None:
    """Окна 24/48/72ч считают только приросты внутри окна."""
    now = datetime(2026, 7, 13, 12, 0, tzinfo=UTC)
    snapshots = [
        _snap(at=now - timedelta(hours=80), total_views=100),
        _snap(at=now - timedelta(hours=60), total_views=110),  # +10 вне 48/24
        _snap(at=now - timedelta(hours=30), total_views=125),  # +15 в 48/72
        _snap(at=now - timedelta(hours=10), total_views=140),  # +15 в 24/48/72
        _snap(at=now - timedelta(hours=1), total_views=150),  # +10 в 24/48/72
    ]
    v24, v48, v72 = period_view_windows(snapshots, now=now)
    assert v24 == 25
    assert v48 == 40
    assert v72 == 50
