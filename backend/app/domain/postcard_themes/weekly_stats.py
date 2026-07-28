"""Недельная статистика использования категорий."""

from __future__ import annotations

import json
from datetime import date

from app.domain.postcard_themes.models import CategoryManifest, PostcardTheme


def iso_week_key(target: date) -> str:
    """Ключ ISO-недели (год-Www)."""
    year, week, _ = target.isocalendar()
    return f"{year}-W{week:02d}"


def parse_week_stats(raw: str) -> tuple[str, dict[str, int]]:
    """Парсит JSON недельной статистики.

    Returns:
        tuple[str, dict[str, int]]: (week_key, counts_by_group).
    """
    if not raw.strip():
        return "", {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return "", {}
    if not isinstance(data, dict):
        return "", {}
    week_key = str(data.get("week_key", "")).strip()
    counts_raw = data.get("counts", {})
    counts: dict[str, int] = {}
    if isinstance(counts_raw, dict):
        for key, value in counts_raw.items():
            counts[str(key)] = int(value)
    return week_key, counts


def serialize_week_stats(week_key: str, counts: dict[str, int]) -> str:
    """Сериализует недельную статистику."""
    return json.dumps(
        {"week_key": week_key, "counts": counts},
        ensure_ascii=False,
    )


def record_category_use(
    manifest: CategoryManifest,
    counts: dict[str, int],
    theme: PostcardTheme,
) -> dict[str, int]:
    """Увеличивает счётчик группы категории."""
    group = manifest.group_for_category(theme.category)
    updated = dict(counts)
    updated[group] = updated.get(group, 0) + 1
    return updated


def category_weight(
    group: str,
    *,
    manifest: CategoryManifest,
    week_counts: dict[str, int],
    today_counts: dict[str, int],
    target_date: date,
    last_groups: list[str],
) -> float:
    """Вес категории для взвешенного случайного выбора."""
    weight = 10.0

    used_today = today_counts.get(group, 0)
    if used_today > 0:
        weight /= 1 + used_today

    streak_limit = manifest.max_same_category_streak
    if len(last_groups) >= streak_limit and all(
        g == group for g in last_groups[-streak_limit:]
    ):
        weight *= 0.1

    if group in manifest.weekly_required_groups and week_counts.get(group, 0) == 0:
        weekday_boost = 1.0 + (target_date.weekday() / 6.0) * 2.0
        weight *= weekday_boost * 3.0

    return max(weight, 0.01)
