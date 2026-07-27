"""Ключи и значения по умолчанию настроек платформы в БД."""

import re
from dataclasses import dataclass
from datetime import datetime

from app.domain.article import (
    ARTICLE_SCHEDULER_KEY_PREFIX,
    ARTICLE_TOPIC_HISTORY_PREFIX,
)
from app.domain.curated_pick import CURATED_PICK_HISTORY_KEY
from app.domain.enums import Topic

_OPENAI_MODEL_NAME_RE = re.compile(r"^[A-Za-z0-9._:-]{2,100}$")


def is_valid_openai_model_name(value: str) -> bool:
    """Return whether a Responses API model identifier is safe to persist."""
    return bool(_OPENAI_MODEL_NAME_RE.fullmatch(value.strip()))


def curated_scheduler_key(topic: str) -> str:
    """Ключ БД для времени последнего curated-запуска по теме.

    Args:
        topic: it | auto | russia | sport.

    Returns:
        str: ключ settings.
    """
    return f"scheduler_last_curated_{topic}"


SCHEDULER_INTERNAL_KEYS: frozenset[str] = frozenset(
    {
        "scheduler_last_fetch_at",
        "scheduler_last_retention_at",
        "scheduler_last_analytics_at",
        CURATED_PICK_HISTORY_KEY,
        *{curated_scheduler_key(t.value) for t in Topic},
    }
)


def is_internal_setting_key(key: str) -> bool:
    """Проверяет, является ли ключ служебным (не редактируется через PATCH).

    Args:
        key: ключ настройки.

    Returns:
        bool: True если ключ служебный.
    """
    if key in SCHEDULER_INTERNAL_KEYS:
        return True
    if key.startswith(ARTICLE_SCHEDULER_KEY_PREFIX):
        return True
    if key.startswith(ARTICLE_TOPIC_HISTORY_PREFIX):
        return True
    return False

PLATFORM_SETTINGS_DEFAULTS: dict[str, str] = {
    # Автоматика по расписанию (Celery Beat → platform_scheduler_tick)
    "schedule_fetch_enabled": "true",
    "schedule_ai_enabled": "false",
    "schedule_publish_enabled": "false",
    "schedule_retention_enabled": "true",
    "schedule_curated_publish_enabled": "true",
    "schedule_article_publish_enabled": "false",
    "schedule_analytics_enabled": "false",
    # Ручные действия из панели
    "manual_fetch_enabled": "true",
    "manual_ai_enabled": "true",
    "manual_publish_enabled": "true",
    "auto_ai_after_manual_fetch": "true",
    # Интервалы и окна
    "fetch_interval_minutes": "30",
    "analytics_interval_minutes": "180",
    "retention_hour_utc": "3",
    "retention_minute_utc": "30",
    "raw_posts_retention_days": "3",
    "fetch_max_age_days": "1",
    # Модерация и AI
    "auto_approve": "false",
    "posts_per_day": "10",
    "rewrite_language": "ru",
    "qwen_image_models": (
        "qwen-image-plus,qwen-image-max,qwen-image,"
        "qwen-image-2.0-pro,qwen-image-2.0,z-image-turbo"
    ),
    "qwen_image_edit_models": (
        "qwen-image-edit-plus,qwen-image-edit-max,qwen-image-edit"
    ),
    # Tavily: доп. ключи в панели + активный + автопереключение
    "tavily_api_keys": "[]",
    "tavily_active_key_id": "",
    "tavily_auto_switch": "true",
    # OpenAI: ключи для gpt-image-2 (открытки и fallback обложек).
    "openai_api_keys": "[]",
    # OpenRouter: анимация открыток (Grok Imagine Video).
    "openrouter_api_key": "",
    "openrouter_api_keys": "[]",
    "openrouter_video_model": "x-ai/grok-imagine-video",
    "postcard_animation_enabled": "true",
    "postcard_animation_duration": "2",
    CURATED_PICK_HISTORY_KEY: "[]",
}


def _parse_bool(value: str, default: bool = False) -> bool:
    """Парсит строковое значение настройки в bool."""
    if value.lower() in ("true", "1", "yes", "on"):
        return True
    if value.lower() in ("false", "0", "no", "off"):
        return False
    return default


def _parse_int(value: str, default: int) -> int:
    """Парсит строковое значение настройки в int."""
    try:
        return int(value)
    except ValueError:
        return default


def clamp_postcard_animation_duration(value: str | int, *, default: int = 2) -> int:
    """Ограничивает длительность анимации открытки диапазоном Grok (1–15 сек)."""
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        seconds = default
    return max(1, min(15, seconds))


@dataclass(frozen=True)
class PlatformSettings:
    """Типизированный снимок настроек платформы из БД."""

    schedule_fetch_enabled: bool
    schedule_ai_enabled: bool
    schedule_publish_enabled: bool
    schedule_retention_enabled: bool
    schedule_curated_publish_enabled: bool
    schedule_article_publish_enabled: bool
    schedule_analytics_enabled: bool
    manual_fetch_enabled: bool
    manual_ai_enabled: bool
    manual_publish_enabled: bool
    auto_ai_after_manual_fetch: bool
    auto_approve: bool
    fetch_interval_minutes: int
    analytics_interval_minutes: int
    retention_hour_utc: int
    retention_minute_utc: int
    raw_posts_retention_days: int
    fetch_max_age_days: int
    posts_per_day: int
    rewrite_language: str
    scheduler_last_fetch_at: datetime | None
    scheduler_last_retention_at: str | None
    scheduler_last_analytics_at: datetime | None
    raw: dict[str, str]

    @classmethod
    def from_merged(cls, merged: dict[str, str]) -> "PlatformSettings":
        """Собирает настройки из словаря (дефолты + БД).

        Args:
            merged: полный словарь key → value.

        Returns:
            PlatformSettings: снимок для задач и API.
        """
        last_fetch: datetime | None = None
        raw_fetch = merged.get("scheduler_last_fetch_at", "").strip()
        if raw_fetch:
            try:
                last_fetch = datetime.fromisoformat(raw_fetch)
            except ValueError:
                last_fetch = None

        last_retention = merged.get("scheduler_last_retention_at", "").strip() or None

        last_analytics: datetime | None = None
        raw_analytics = merged.get("scheduler_last_analytics_at", "").strip()
        if raw_analytics:
            try:
                last_analytics = datetime.fromisoformat(raw_analytics)
            except ValueError:
                last_analytics = None

        return cls(
            schedule_fetch_enabled=_parse_bool(
                merged.get("schedule_fetch_enabled", "true"), True
            ),
            schedule_ai_enabled=_parse_bool(
                merged.get("schedule_ai_enabled", "false"), False
            ),
            schedule_publish_enabled=_parse_bool(
                merged.get("schedule_publish_enabled", "false"), False
            ),
            schedule_retention_enabled=_parse_bool(
                merged.get("schedule_retention_enabled", "true"), True
            ),
            schedule_curated_publish_enabled=_parse_bool(
                merged.get("schedule_curated_publish_enabled", "true"), True
            ),
            schedule_article_publish_enabled=_parse_bool(
                merged.get("schedule_article_publish_enabled", "false"), False
            ),
            schedule_analytics_enabled=_parse_bool(
                merged.get("schedule_analytics_enabled", "false"), False
            ),
            manual_fetch_enabled=_parse_bool(
                merged.get("manual_fetch_enabled", "true"), True
            ),
            manual_ai_enabled=_parse_bool(
                merged.get("manual_ai_enabled", "true"), True
            ),
            manual_publish_enabled=_parse_bool(
                merged.get("manual_publish_enabled", "true"), True
            ),
            auto_ai_after_manual_fetch=_parse_bool(
                merged.get("auto_ai_after_manual_fetch", "true"), True
            ),
            auto_approve=_parse_bool(merged.get("auto_approve", "false"), False),
            fetch_interval_minutes=_parse_int(
                merged.get("fetch_interval_minutes", "30"), 30
            ),
            analytics_interval_minutes=_parse_int(
                merged.get("analytics_interval_minutes", "180"), 180
            ),
            retention_hour_utc=_parse_int(merged.get("retention_hour_utc", "3"), 3),
            retention_minute_utc=_parse_int(
                merged.get("retention_minute_utc", "30"), 30
            ),
            raw_posts_retention_days=_parse_int(
                merged.get("raw_posts_retention_days", "3"), 3
            ),
            fetch_max_age_days=_parse_int(merged.get("fetch_max_age_days", "1"), 1),
            posts_per_day=_parse_int(merged.get("posts_per_day", "10"), 10),
            rewrite_language=merged.get("rewrite_language", "ru"),
            scheduler_last_fetch_at=last_fetch,
            scheduler_last_retention_at=last_retention,
            scheduler_last_analytics_at=last_analytics,
            raw=merged,
        )

    def should_queue_ai_after_fetch(self, manual: bool) -> bool:
        """Нужно ли ставить новые raw_posts на AI после парсинга.

        Args:
            manual: True если парсинг запущен кнопкой «Парсить».

        Returns:
            bool: ставить process_post в очередь.
        """
        if manual:
            return self.auto_ai_after_manual_fetch
        return self.schedule_ai_enabled
