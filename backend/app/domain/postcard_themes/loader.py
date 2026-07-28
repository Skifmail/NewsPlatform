"""Загрузка JSON-каталога тем открыток."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from datetime import date

from app.domain.postcard_themes.date_parser import annual_key, parse_holiday_date
from app.domain.postcard_themes.models import CategoryManifest, PostcardTheme


class PostcardThemeCatalog:
    """Каталог тем и праздников, загружаемый из JSON-файлов."""

    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._manifest = self._load_manifest()
        self._themes = self._load_themes()
        self._annual_holidays, self._year_holidays = self._load_holidays()

    @property
    def manifest(self) -> CategoryManifest:
        """Конфигурация категорий."""
        return self._manifest

    @property
    def themes(self) -> list[PostcardTheme]:
        """Все непраздничные темы."""
        return list(self._themes)

    def themes_by_category(self, category: str) -> list[PostcardTheme]:
        """Темы одной категории или группы категорий."""
        members = self._categories_for_group(category)
        return [t for t in self._themes if t.category in members]

    def themes_by_group(self, group: str) -> list[PostcardTheme]:
        """Темы, входящие в группу недельного покрытия."""
        return self.themes_by_category(group)

    def holidays_for_date(self, target: date) -> list[PostcardTheme]:
        """Праздники на указанную дату, отсортированные по приоритету."""
        found: list[PostcardTheme] = []
        key = annual_key(target.month, target.day)
        for item in self._annual_holidays.get(key, ()):
            found.append(item)
        for item in self._year_holidays.get(target, ()):
            found.append(item)
        found.sort(
            key=lambda t: (
                self._manifest.holiday_sort_key(t.category),
                t.name,
            )
        )
        return found

    def _categories_for_group(self, group: str) -> set[str]:
        members = self._manifest.category_groups.get(group)
        if members:
            return set(members)
        return {group}

    def _load_manifest(self) -> CategoryManifest:
        path = self._base_dir / "manifest.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        category_groups = {
            group: tuple(members)
            for group, members in raw.get("category_groups", {}).items()
        }
        return CategoryManifest(
            holiday_priority=tuple(raw.get("holiday_priority", ())),
            first_slot_fallback_groups=tuple(
                raw.get("first_slot_fallback_groups", ())
            ),
            weekly_required_groups=tuple(raw.get("weekly_required_groups", ())),
            category_groups=category_groups,
            history_min_gap_days=int(raw.get("history_min_gap_days", 30)),
            max_same_category_streak=int(raw.get("max_same_category_streak", 2)),
        )

    def _load_themes(self) -> tuple[PostcardTheme, ...]:
        themes_dir = self._base_dir / "themes"
        result: list[PostcardTheme] = []
        if not themes_dir.is_dir():
            return tuple(result)
        for path in sorted(themes_dir.glob("*.json")):
            items = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(items, list):
                continue
            for item in items:
                name = str(item.get("name", "")).strip()
                category = str(item.get("category", "")).strip()
                if name and category:
                    result.append(PostcardTheme(name=name, category=category))
        return tuple(result)

    def _load_holidays(
        self,
    ) -> tuple[dict[tuple[int, int], tuple[PostcardTheme, ...]], dict[date, tuple[PostcardTheme, ...]]]:
        holidays_dir = self._base_dir / "holidays"
        annual: dict[tuple[int, int], list[PostcardTheme]] = {}
        by_year: dict[date, list[PostcardTheme]] = {}
        if not holidays_dir.is_dir():
            return {}, {}

        annual_path = holidays_dir / "annual.json"
        if annual_path.is_file():
            for item in json.loads(annual_path.read_text(encoding="utf-8")):
                theme = self._parse_holiday_item(item)
                if theme is None:
                    continue
                parsed = parse_holiday_date(str(item["date"]), year=2000)
                key = annual_key(parsed.month, parsed.day)
                annual.setdefault(key, []).append(theme)

        for path in sorted(holidays_dir.glob("*.json")):
            if path.name == "annual.json":
                continue
            year_str = path.stem
            if not year_str.isdigit():
                continue
            year = int(year_str)
            for item in json.loads(path.read_text(encoding="utf-8")):
                theme = self._parse_holiday_item(item)
                if theme is None:
                    continue
                parsed = parse_holiday_date(str(item["date"]), year=year)
                by_year.setdefault(parsed, []).append(theme)

        annual_tuple = {key: tuple(items) for key, items in annual.items()}
        year_tuple = {key: tuple(items) for key, items in by_year.items()}
        return annual_tuple, year_tuple

    @staticmethod
    def _parse_holiday_item(item: object) -> PostcardTheme | None:
        if not isinstance(item, dict):
            return None
        name = str(item.get("name", "")).strip()
        category = str(item.get("category", "")).strip()
        if not name or not category or "date" not in item:
            return None
        return PostcardTheme(
            name=name,
            category=category,
            is_holiday=True,
            mandatory=True,
        )


@lru_cache(maxsize=4)
def get_postcard_theme_catalog(base_dir: str) -> PostcardThemeCatalog:
    """Кэшированный каталог по пути к данным."""
    return PostcardThemeCatalog(Path(base_dir))
