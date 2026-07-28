"""Детерминированный календарь праздников для канала открыток.

.. deprecated::
    Используйте ``app.domain.postcard_themes`` и JSON-каталог
    ``data/postcard_themes/holidays/``. Модуль сохранён как тонкая обёртка
    для обратной совместимости.
"""

from __future__ import annotations

import warnings
from datetime import date

from app.core.config import get_settings
from app.domain.postcard_themes.loader import get_postcard_theme_catalog


def today_holiday(today: date | None = None) -> str:
    """Официальный/общепринятый праздник на указанную дату.

    Args:
        today: дата проверки. По умолчанию — текущая дата.

    Returns:
        str: название праздника или "" (обычный день).
    """
    warnings.warn(
        "postcard_calendar.today_holiday is deprecated; use postcard_themes catalog",
        DeprecationWarning,
        stacklevel=2,
    )
    day = today or date.today()
    catalog = get_postcard_theme_catalog(str(get_settings().postcard_themes_dir))
    holidays = catalog.holidays_for_date(day)
    if not holidays:
        return ""
    return holidays[0].name
