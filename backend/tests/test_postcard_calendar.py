"""Тесты обёртки postcard_calendar (делегирует в JSON-каталог)."""

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
        (date(2026, 5, 9), "День Победы советского народа в Великой Отечественной войне 1941-1945 годов"),
        (date(2026, 6, 12), "День России"),
        (date(2026, 9, 1), "День знаний"),
        (date(2026, 11, 4), "День народного единства"),
        (date(2026, 12, 31), "Новый год"),
    ],
)
def test_fixed_holiday_detected(day: date, expected: str) -> None:
    with pytest.warns(DeprecationWarning):
        assert today_holiday(day) == expected


@pytest.mark.parametrize(
    "day",
    [
        date(2026, 7, 28),
        date(2026, 1, 2),
        date(2026, 4, 15),
        date(2026, 8, 1),
    ],
)
def test_ordinary_day_has_no_holiday(day: date) -> None:
    with pytest.warns(DeprecationWarning):
        assert today_holiday(day) == ""


def test_mothers_day_from_year_catalog() -> None:
    with pytest.warns(DeprecationWarning):
        assert today_holiday(date(2026, 11, 29)) == "День матери"
