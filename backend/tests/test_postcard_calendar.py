"""Тесты детерминированного календаря праздников для канала открыток."""

from datetime import date

import pytest

from app.domain.postcard_calendar import today_holiday


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        (date(2026, 1, 1), "Новый год"),
        (date(2026, 1, 7), "Рождество Христово"),
        (date(2026, 2, 23), "День защитника Отечества"),
        (date(2026, 3, 8), "Международный женский день"),
        (date(2026, 5, 1), "Праздник Весны и Труда"),
        (date(2026, 5, 9), "День Победы"),
        (date(2026, 6, 12), "День России"),
        (date(2026, 9, 1), "День знаний"),
        (date(2026, 10, 5), "День учителя"),
        (date(2026, 11, 4), "День народного единства"),
        (date(2026, 12, 31), "Новый год (канун)"),
    ],
)
def test_fixed_holiday_detected(day: date, expected: str) -> None:
    assert today_holiday(day) == expected


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 7, 26),
        date(2026, 1, 2),
        date(2026, 4, 15),
        date(2026, 8, 1),
    ],
)
def test_ordinary_day_has_no_holiday(day: date) -> None:
    assert today_holiday(day) == ""


@pytest.mark.parametrize(
    ("year", "expected_day"),
    [
        (2024, 24),
        (2025, 30),
        (2026, 29),
        (2027, 28),
    ],
)
def test_mothers_day_is_last_sunday_of_november(year: int, expected_day: int) -> None:
    assert today_holiday(date(year, 11, expected_day)) == "День матери"
    # день до плавающей даты — обычный день, а не праздник.
    if expected_day > 1:
        assert today_holiday(date(year, 11, expected_day - 1)) == ""


def test_defaults_to_current_date_when_no_argument() -> None:
    # Явно не праздничная дата не ломает вызов без аргумента (сигнатура).
    assert today_holiday() == today_holiday(date.today())
