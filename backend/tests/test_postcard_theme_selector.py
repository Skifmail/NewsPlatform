"""Тесты детерминированного выбора тем открыток."""

from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.domain.postcard_themes.date_parser import parse_holiday_date
from app.domain.postcard_themes.history import (
    ThemeHistoryEntry,
    filter_allowed_themes,
    is_theme_allowed,
)
from app.domain.postcard_themes.loader import PostcardThemeCatalog
from app.domain.postcard_themes.models import PostcardTheme
from app.domain.postcard_themes.selector import PostcardThemeSelector
from app.domain.postcard_themes.weekly_stats import category_weight


@pytest.fixture
def catalog() -> PostcardThemeCatalog:
    settings = get_settings()
    return PostcardThemeCatalog(settings.postcard_themes_dir)


def test_parse_russian_and_iso_dates() -> None:
    assert parse_holiday_date("7 января", year=2026) == date(2026, 1, 7)
    assert parse_holiday_date("2026-04-12", year=2026) == date(2026, 4, 12)


def test_multiple_holidays_sorted_by_priority(catalog: PostcardThemeCatalog) -> None:
    holidays = catalog.holidays_for_date(date(2026, 4, 7))
    names = [h.name for h in holidays]
    assert "Благовещение Пресвятой Богородицы" in names
    assert holidays[0].category == "православный праздник"


def test_annunciation_and_professional_on_same_day(catalog: PostcardThemeCatalog) -> None:
  # 15 февраля: Сретение + день памяти
    holidays = catalog.holidays_for_date(date(2026, 2, 15))
    assert len(holidays) >= 2
    categories = [h.category for h in holidays]
    assert "православный праздник" in categories
    assert categories.index("православный праздник") < categories.index("день памяти")


def test_ordinary_day_first_slot_from_fallback_groups(catalog: PostcardThemeCatalog) -> None:
    rng = random.Random(42)
    selector = PostcardThemeSelector(catalog, rng=rng)
    plan = selector.build_daily_plan(date(2026, 7, 28), 4, [], {})
    assert plan.slots
    first = plan.slots[0]
    assert first.category in catalog.manifest.first_slot_fallback_groups


def test_holiday_day_starts_with_mandatory_holidays(catalog: PostcardThemeCatalog) -> None:
    selector = PostcardThemeSelector(catalog, rng=random.Random(1))
    plan = selector.build_daily_plan(date(2026, 6, 12), 4, [], {})
    assert plan.slots[0].name == "День России"
    assert plan.slots[0].mandatory is True


def test_weekly_missing_group_gets_higher_weight(catalog: PostcardThemeCatalog) -> None:
    manifest = catalog.manifest
    base = category_weight(
        "романтические открытки",
        manifest=manifest,
        week_counts={},
        today_counts={},
        target_date=date(2026, 7, 24),  # Friday
        last_groups=[],
    )
    covered = category_weight(
        "романтические открытки",
        manifest=manifest,
        week_counts={"романтические открытки": 2},
        today_counts={},
        target_date=date(2026, 7, 24),
        last_groups=[],
    )
    assert base > covered


def test_blocks_same_theme_yesterday() -> None:
    theme = PostcardTheme(name="Доброе утро", category="повседневные открытки")
    today = date(2026, 7, 28)
    history = [
        ThemeHistoryEntry(name="Доброе утро", category="повседневные открытки", published_on=today - timedelta(days=1)),
    ]
    assert not is_theme_allowed(theme, target_date=today, history=history, min_gap_days=30)


def test_30_day_gap_relaxed_when_needed(catalog: PostcardThemeCatalog) -> None:
    theme = PostcardTheme(name="Счастья", category="универсальные пожелания")
    today = date(2026, 7, 28)
    history = [
        ThemeHistoryEntry(name="Счастья", category="универсальные пожелания", published_on=today - timedelta(days=10)),
    ]
    allowed = filter_allowed_themes(
        [theme],
        target_date=today,
        history=history,
        min_gap_days=30,
    )
    assert allowed == [theme]


def test_loader_reads_extra_json_file(tmp_path: Path) -> None:
    manifest = {
        "holiday_priority": ["тестовая категория"],
        "first_slot_fallback_groups": ["тестовая категория"],
        "weekly_required_groups": ["тестовая категория"],
        "category_groups": {},
        "history_min_gap_days": 30,
        "max_same_category_streak": 2,
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "themes").mkdir()
    (tmp_path / "themes" / "custom.json").write_text(
        json.dumps([{"name": "Тест", "category": "тестовая категория"}]),
        encoding="utf-8",
    )
    (tmp_path / "holidays").mkdir()
    (tmp_path / "holidays" / "annual.json").write_text("[]", encoding="utf-8")
    cat = PostcardThemeCatalog(tmp_path)
    assert any(t.name == "Тест" for t in cat.themes)


def test_plan_expands_when_more_holidays_than_slots(catalog: PostcardThemeCatalog) -> None:
    selector = PostcardThemeSelector(catalog, rng=random.Random(0))
    plan = selector.build_daily_plan(date(2026, 10, 25), 1, [], {})
    assert len(plan.slots) >= 3
