"""Детерминированный календарь праздников для канала открыток.

Даты — факт, а не то, что должна «угадывать» LLM (модели галлюцинируют
дни недели и путают числа). Идеация получает готовый результат этой
функции как переменную {today_holiday}, а не сам вычисляет дату.
"""

from datetime import date, timedelta

_FIXED_HOLIDAYS: dict[tuple[int, int], str] = {
    (1, 1): "Новый год",
    (1, 7): "Рождество Христово",
    (2, 23): "День защитника Отечества",
    (3, 8): "Международный женский день",
    (5, 1): "Праздник Весны и Труда",
    (5, 9): "День Победы",
    (6, 12): "День России",
    (9, 1): "День знаний",
    (10, 5): "День учителя",
    (11, 4): "День народного единства",
    (12, 31): "Новый год (канун)",
}


def today_holiday(today: date | None = None) -> str:
    """Официальный/общепринятый праздник на указанную дату.

    Args:
        today: дата проверки. По умолчанию — текущая дата.

    Returns:
        str: название праздника или "" (обычный день).
    """
    day = today or date.today()
    fixed = _FIXED_HOLIDAYS.get((day.month, day.day))
    if fixed:
        return fixed
    if day == _last_sunday_of_november(day.year):
        return "День матери"
    return ""


def _last_sunday_of_november(year: int) -> date:
    """Последнее воскресенье ноября (плавающая дата Дня матери в РФ)."""
    last_day = date(year, 11, 30)
    offset = (last_day.weekday() - 6) % 7
    return last_day - timedelta(days=offset)
