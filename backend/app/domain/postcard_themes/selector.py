"""Алгоритм построения дневного плана и выбора тем."""

from __future__ import annotations

import random
from datetime import date

from loguru import logger

from app.domain.postcard_themes.history import filter_allowed_themes
from app.domain.postcard_themes.loader import PostcardThemeCatalog
from app.domain.postcard_themes.models import DailyPlan, PostcardTheme, ThemeHistoryEntry
from app.domain.postcard_themes.weekly_stats import category_weight


class PostcardThemeSelector:
    """Детерминированный выбор тем открыток."""

    def __init__(
        self,
        catalog: PostcardThemeCatalog,
        *,
        rng: random.Random | None = None,
    ) -> None:
        self._catalog = catalog
        self._rng = rng or random.Random()

    def build_daily_plan(
        self,
        target_date: date,
        slots_count: int,
        history: list[ThemeHistoryEntry],
        week_counts: dict[str, int],
    ) -> DailyPlan:
        """Строит план тем на день.

        Args:
            target_date: дата публикаций.
            slots_count: число слотов publish_times.
            history: история опубликованных тем.
            week_counts: счётчики групп за текущую неделю.

        Returns:
            DailyPlan: план с обязательными праздниками и заполнением.
        """
        manifest = self._catalog.manifest
        holidays = self._catalog.holidays_for_date(target_date)
        plan_size = max(slots_count, len(holidays), 1)
        if len(holidays) > slots_count:
            logger.warning(
                "Postcard holidays exceed daily slots; plan expanded",
                holidays=len(holidays),
                slots=slots_count,
                date=target_date.isoformat(),
            )

        slots: list[PostcardTheme] = [
            PostcardTheme(
                name=h.name,
                category=h.category,
                is_holiday=True,
                mandatory=True,
            )
            for h in holidays
        ]
        today_counts: dict[str, int] = {}
        last_groups: list[str] = []
        for h in holidays:
            group = manifest.group_for_category(h.category)
            today_counts[group] = today_counts.get(group, 0) + 1
            last_groups.append(group)

        filler_needed = plan_size - len(slots)
        used_names_today = {s.name for s in slots}

        for index in range(filler_needed):
            if not holidays and index == 0:
                theme = self._pick_from_groups(
                    manifest.first_slot_fallback_groups,
                    target_date=target_date,
                    history=history,
                    week_counts=week_counts,
                    today_counts=today_counts,
                    last_groups=last_groups,
                    exclude_names=used_names_today,
                )
            else:
                theme = self._pick_balanced_theme(
                    target_date=target_date,
                    history=history,
                    week_counts=week_counts,
                    today_counts=today_counts,
                    last_groups=last_groups,
                    exclude_names=used_names_today,
                )
            if theme is None:
                logger.warning(
                    "Could not fill postcard plan slot",
                    slot_index=len(slots),
                    date=target_date.isoformat(),
                )
                break
            slots.append(theme)
            used_names_today.add(theme.name)
            group = manifest.group_for_category(theme.category)
            today_counts[group] = today_counts.get(group, 0) + 1
            last_groups.append(group)

        return DailyPlan(plan_date=target_date, slots=slots)

    def _pick_balanced_theme(
        self,
        *,
        target_date: date,
        history: list[ThemeHistoryEntry],
        week_counts: dict[str, int],
        today_counts: dict[str, int],
        last_groups: list[str],
        exclude_names: set[str],
    ) -> PostcardTheme | None:
        manifest = self._catalog.manifest
        groups = list(manifest.weekly_required_groups)
        weights = [
            category_weight(
                group,
                manifest=manifest,
                week_counts=week_counts,
                today_counts=today_counts,
                target_date=target_date,
                last_groups=last_groups,
            )
            for group in groups
        ]
        ordered_groups = sorted(
            groups,
            key=lambda g: category_weight(
                g,
                manifest=manifest,
                week_counts=week_counts,
                today_counts=today_counts,
                target_date=target_date,
                last_groups=last_groups,
            ),
            reverse=True,
        )
        # weighted random over groups
        total = sum(weights)
        pick = self._rng.uniform(0, total)
        cumulative = 0.0
        chosen_group = ordered_groups[0]
        for group, weight in zip(groups, weights, strict=True):
            cumulative += weight
            if pick <= cumulative:
                chosen_group = group
                break
        return self._pick_from_groups(
            (chosen_group,),
            target_date=target_date,
            history=history,
            week_counts=week_counts,
            today_counts=today_counts,
            last_groups=last_groups,
            exclude_names=exclude_names,
        )

    def _pick_from_groups(
        self,
        groups: tuple[str, ...] | list[str],
        *,
        target_date: date,
        history: list[ThemeHistoryEntry],
        week_counts: dict[str, int],
        today_counts: dict[str, int],
        last_groups: list[str],
        exclude_names: set[str],
    ) -> PostcardTheme | None:
        manifest = self._catalog.manifest
        group_list = list(groups)
        self._rng.shuffle(group_list)
        for group in group_list:
            candidates = [
                t
                for t in self._catalog.themes_by_group(group)
                if t.name not in exclude_names
            ]
            allowed = filter_allowed_themes(
                candidates,
                target_date=target_date,
                history=history,
                min_gap_days=manifest.history_min_gap_days,
            )
            if allowed:
                return self._rng.choice(allowed)
        # fallback: any theme
        all_candidates = [
            t for t in self._catalog.themes if t.name not in exclude_names
        ]
        allowed = filter_allowed_themes(
            all_candidates,
            target_date=target_date,
            history=history,
            min_gap_days=manifest.history_min_gap_days,
        )
        if allowed:
            return self._rng.choice(allowed)
        return None
