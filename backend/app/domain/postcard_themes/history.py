"""История публикаций тем открыток и антиповторы."""

from __future__ import annotations

import json
from datetime import date, timedelta

from app.domain.postcard_themes.models import PostcardTheme, ThemeHistoryEntry


def parse_theme_history(raw: str) -> list[ThemeHistoryEntry]:
    """Парсит JSON-историю тем из settings."""
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    result: list[ThemeHistoryEntry] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        category = str(item.get("category", "")).strip()
        published_raw = str(item.get("published_on", "")).strip()
        if not name or not published_raw:
            continue
        try:
            published_on = date.fromisoformat(published_raw)
        except ValueError:
            continue
        result.append(
            ThemeHistoryEntry(
                name=name,
                category=category or "",
                published_on=published_on,
            )
        )
    return result


def serialize_theme_history(entries: list[ThemeHistoryEntry], *, limit: int = 200) -> str:
    """Сериализует историю тем в JSON."""
    payload = [
        {
            "name": e.name,
            "category": e.category,
            "published_on": e.published_on.isoformat(),
        }
        for e in entries[:limit]
    ]
    return json.dumps(payload, ensure_ascii=False)


def is_theme_allowed(
    theme: PostcardTheme,
    *,
    target_date: date,
    history: list[ThemeHistoryEntry],
    min_gap_days: int,
) -> bool:
    """Проверяет, можно ли публиковать тему с учётом истории."""
    for entry in history:
        if entry.name != theme.name:
            continue
        if entry.published_on == target_date:
            return False
        if entry.published_on == target_date - timedelta(days=1):
            return False
        gap = (target_date - entry.published_on).days
        if 0 < gap < min_gap_days:
            return False
    return True


def filter_allowed_themes(
    candidates: list[PostcardTheme],
    *,
    target_date: date,
    history: list[ThemeHistoryEntry],
    min_gap_days: int,
) -> list[PostcardTheme]:
    """Фильтрует кандидатов с каскадным ослаблением gap (30 → 7 → 0)."""
    for gap in (min_gap_days, 7, 0):
        allowed = [
            t
            for t in candidates
            if is_theme_allowed(
                t,
                target_date=target_date,
                history=history,
                min_gap_days=gap if gap > 0 else 0,
            )
        ]
        if allowed:
            return allowed
    return candidates
