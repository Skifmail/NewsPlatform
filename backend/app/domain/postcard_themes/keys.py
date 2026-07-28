"""Ключи settings для состояния выбора тем открыток."""

POSTCARD_DAILY_PLAN_PREFIX = "postcard_daily_plan_"
POSTCARD_WEEK_STATS_PREFIX = "postcard_week_stats_"
POSTCARD_THEME_HISTORY_PREFIX = "postcard_theme_history_"


def postcard_daily_plan_key(channel_id: int) -> str:
    """Ключ дневного плана тем канала."""
    return f"{POSTCARD_DAILY_PLAN_PREFIX}{channel_id}"


def postcard_week_stats_key(channel_id: int) -> str:
    """Ключ недельной статистики категорий канала."""
    return f"{POSTCARD_WEEK_STATS_PREFIX}{channel_id}"


def postcard_theme_history_key(channel_id: int) -> str:
    """Ключ истории опубликованных тем канала."""
    return f"{POSTCARD_THEME_HISTORY_PREFIX}{channel_id}"
