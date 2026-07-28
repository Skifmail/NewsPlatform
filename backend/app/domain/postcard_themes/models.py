"""Доменные модели каталога тем открыток."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass(frozen=True)
class PostcardTheme:
    """Тема открытки из JSON-каталога."""

    name: str
    category: str
    is_holiday: bool = False
    mandatory: bool = False


@dataclass(frozen=True)
class ThemeHistoryEntry:
    """Запись об опубликованной теме."""

    name: str
    category: str
    published_on: date


@dataclass(frozen=True)
class CategoryManifest:
    """Конфигурация категорий из manifest.json."""

    holiday_priority: tuple[str, ...]
    first_slot_fallback_groups: tuple[str, ...]
    weekly_required_groups: tuple[str, ...]
    category_groups: dict[str, tuple[str, ...]]
    history_min_gap_days: int = 30
    max_same_category_streak: int = 2

    def group_for_category(self, category: str) -> str:
        """Возвращает группу недельного покрытия для категории темы."""
        for group, members in self.category_groups.items():
            if category in members:
                return group
        return category

    def holiday_sort_key(self, category: str) -> int:
        """Индекс приоритета праздничной категории (меньше — выше)."""
        try:
            return self.holiday_priority.index(category)
        except ValueError:
            return len(self.holiday_priority)


@dataclass
class DailyPlan:
    """Дневной план тем для канала."""

    plan_date: date
    slots: list[PostcardTheme] = field(default_factory=list)
    next_index: int = 0

    def remaining(self) -> list[PostcardTheme]:
        """Темы, ещё не выданные из плана."""
        return self.slots[self.next_index :]

    def pop_next(self) -> PostcardTheme | None:
        """Забирает следующую тему из плана."""
        if self.next_index >= len(self.slots):
            return None
        theme = self.slots[self.next_index]
        self.next_index += 1
        return theme
