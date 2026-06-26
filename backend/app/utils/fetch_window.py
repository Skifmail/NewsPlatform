"""Окно свежести материалов при парсинге."""

from datetime import UTC, datetime, timedelta


def fetch_cutoff_utc(max_age_days: int = 1) -> datetime:
    """Начало окна: полночь UTC ``max_age_days`` календарных дней назад.

    При ``max_age_days=1`` допускаются материалы за вчера и сегодня.

    Args:
        max_age_days: число полных календарных дней в прошлое от сегодня.

    Returns:
        datetime: нижняя граница ``published_at`` (включительно).
    """
    days = max(0, max_age_days)
    today_start = datetime.now(UTC).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    return today_start - timedelta(days=days)


def is_within_fetch_window(
    published_at: datetime | None,
    max_age_days: int = 1,
) -> bool:
    """Проверяет, попадает ли дата публикации в окно «сегодня + вчера».

    Args:
        published_at: дата из источника; без даты материал не принимается.
        max_age_days: глубина окна (1 = вчера и сегодня по UTC).

    Returns:
        bool: True если материал достаточно свежий.
    """
    if published_at is None:
        return False
    moment = published_at
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    return moment >= fetch_cutoff_utc(max_age_days)
