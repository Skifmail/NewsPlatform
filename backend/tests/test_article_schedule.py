"""Тесты расписания статей по конкретным временам (МСК)."""

from datetime import UTC, datetime, timedelta

from app.domain.article_schedule import (
    due_slot,
    format_publish_times,
    parse_publish_times,
)


def _utc(y, mo, d, h, mi):
    return datetime(y, mo, d, h, mi, tzinfo=UTC)


def test_parse_normalizes_sorts_dedups() -> None:
    times = parse_publish_times(" 9:00 , 18:30 , мусор, 09:00 ")
    assert format_publish_times(times) == "09:00,18:30"


def test_parse_empty() -> None:
    assert parse_publish_times("") == []
    assert parse_publish_times(None) == []


def test_msk_slot_converts_to_utc() -> None:
    # 09:00 МСК == 06:00 UTC. now = 06:05 UTC, слот только наступил, не запускался.
    now = _utc(2026, 7, 20, 6, 5)
    slot = due_slot(now, "09:00", None)
    assert slot == _utc(2026, 7, 20, 6, 0)


def test_before_slot_returns_none() -> None:
    # now = 05:30 UTC (08:30 МСК), до слота 09:00 МСК → None
    assert due_slot(_utc(2026, 7, 20, 5, 30), "09:00", None) is None


def test_after_catchup_window_returns_none() -> None:
    # слот 06:00 UTC, catchup 90м, now = 08:00 UTC (спустя 2ч) → None
    assert due_slot(_utc(2026, 7, 20, 8, 0), "09:00", None) is None


def test_already_fired_returns_none() -> None:
    # слот 06:00 UTC уже отрабатывал (last_run 06:01) → None
    now = _utc(2026, 7, 20, 6, 10)
    assert due_slot(now, "09:00", _utc(2026, 7, 20, 6, 1)) is None


def test_fires_once_then_blocks_same_slot() -> None:
    now1 = _utc(2026, 7, 20, 6, 2)
    slot = due_slot(now1, "09:00,18:00", None)
    assert slot == _utc(2026, 7, 20, 6, 0)  # 09:00 МСК
    # после запуска (last_run = now1) тот же слот больше не наступает
    assert due_slot(_utc(2026, 7, 20, 6, 30), "09:00,18:00", now1) is None


def test_second_slot_of_day() -> None:
    # 18:00 МСК == 15:00 UTC. now = 15:10 UTC, утренний уже отработал.
    last = _utc(2026, 7, 20, 6, 1)
    slot = due_slot(_utc(2026, 7, 20, 15, 10), "09:00,18:00", last)
    assert slot == _utc(2026, 7, 20, 15, 0)


def test_late_evening_msk_slot_crosses_utc_midnight() -> None:
    # 23:30 МСК == 20:30 UTC того же дня.
    slot = due_slot(_utc(2026, 7, 20, 20, 35), "23:30", None)
    assert slot == _utc(2026, 7, 20, 20, 30)
