"""Тесты расчёта расходов из истории баланса."""

from datetime import UTC, datetime, timedelta

from app.domain.ai_spend import compute_spend


def _t(hours_ago: float, now: datetime) -> datetime:
    return now - timedelta(hours=hours_ago)


def _d(days_ago: float, now: datetime) -> datetime:
    return now - timedelta(days=days_ago)


def test_empty_and_single_point() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    assert compute_spend([], now).spent_30d == 0.0
    single = compute_spend([(_t(1, now), 5.0)], now)
    assert single.spent_30d == 0.0
    assert len(single.points) == 1


def test_spend_is_sum_of_drops() -> None:
    now = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    series = [
        (_d(20, now), 5.00),  # старт (в 30д)
        (_d(15, now), 4.50),  # -0.50 → только в 30д
        (_d(5, now), 4.20),   # -0.30 → в 30д и 7д
        (_t(12, now), 4.00),  # -0.20 → во всех окнах
    ]
    s = compute_spend(series, now)
    assert round(s.spent_24h, 2) == 0.20
    assert round(s.spent_7d, 2) == 0.50
    assert round(s.spent_30d, 2) == 1.00
    assert s.topped_up_30d == 0.0


def test_topup_counted_separately() -> None:
    now = datetime(2026, 7, 20, 12, 0, tzinfo=UTC)
    series = [
        (_t(10, now), 1.00),
        (_t(5, now), 0.40),   # -0.60 трата
        (_t(3, now), 5.40),   # +5.00 пополнение
        (_t(1, now), 5.10),   # -0.30 трата
    ]
    s = compute_spend(series, now)
    assert round(s.spent_24h, 2) == 0.90  # 0.60 + 0.30
    assert round(s.topped_up_30d, 2) == 5.00


def test_points_limited() -> None:
    now = datetime(2026, 7, 20, tzinfo=UTC)
    series = [(_t(i, now), float(i)) for i in range(200, 0, -1)]
    s = compute_spend(series, now, max_points=10)
    assert len(s.points) == 10
