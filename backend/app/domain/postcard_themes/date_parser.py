"""Парсинг дат праздников из JSON."""

from __future__ import annotations

import re
from datetime import date

_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

_MONTHS: dict[str, int] = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}

_RUSSIAN_DATE_RE = re.compile(
    r"^(\d{1,2})\s+(" + "|".join(_MONTHS) + r")$",
    re.IGNORECASE,
)


def parse_holiday_date(raw: str, *, year: int) -> date:
    """Парсит дату праздника из строки JSON.

    Поддерживает ISO ``YYYY-MM-DD`` и русский формат ``D месяца``.

    Args:
        raw: строка даты из JSON.
        year: календарный год для русского формата.

    Returns:
        date: распознанная дата.

    Raises:
        ValueError: если формат не распознан.
    """
    text = raw.strip()
    iso = _ISO_DATE_RE.match(text)
    if iso:
        return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))

    ru = _RUSSIAN_DATE_RE.match(text.lower())
    if ru:
        day = int(ru.group(1))
        month = _MONTHS[ru.group(2).lower()]
        return date(year, month, day)

    msg = f"Unrecognized holiday date format: {raw!r}"
    raise ValueError(msg)


def annual_key(month: int, day: int) -> tuple[int, int]:
    """Ключ для ежегодного праздника (месяц, день)."""
    return month, day
