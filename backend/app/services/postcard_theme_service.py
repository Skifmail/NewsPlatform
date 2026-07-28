"""Сервис детерминированного выбора тем открыток."""

from __future__ import annotations

import json
from datetime import date

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.article_schedule import parse_publish_times
from app.domain.postcard_themes.history import (
    parse_theme_history,
    serialize_theme_history,
)
from app.domain.postcard_themes.keys import (
    postcard_daily_plan_key,
    postcard_theme_history_key,
    postcard_week_stats_key,
)
from app.domain.postcard_themes.loader import get_postcard_theme_catalog
from app.domain.postcard_themes.models import DailyPlan, PostcardTheme, ThemeHistoryEntry
from app.domain.postcard_themes.selector import PostcardThemeSelector
from app.domain.postcard_themes.weekly_stats import (
    iso_week_key,
    parse_week_stats,
    record_category_use,
    serialize_week_stats,
)
from app.infrastructure.models.channel import Channel
from app.repositories.setting_repository import SettingRepository


class PostcardThemeService:
    """Выбирает тему открытки и ведёт состояние плана/истории."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = SettingRepository(session)
        settings = get_settings()
        self._catalog = get_postcard_theme_catalog(str(settings.postcard_themes_dir))
        self._selector = PostcardThemeSelector(self._catalog)

    async def pick_next(self, channel: Channel, *, target_date: date | None = None) -> PostcardTheme:
        """Возвращает следующую тему из дневного плана канала.

        Args:
            channel: канал-открытка.
            target_date: дата плана (по умолчанию сегодня).

        Returns:
            PostcardTheme: выбранная тема.

        Raises:
            RuntimeError: если план пуст и тему подобрать не удалось.
        """
        day = target_date or date.today()
        plan = await self._load_or_build_plan(channel, day)
        theme = plan.pop_next()
        if theme is None:
            msg = f"Postcard daily plan exhausted for channel {channel.id} on {day}"
            raise RuntimeError(msg)
        await self._save_plan(channel.id, plan)
        logger.info(
            "Postcard theme picked",
            channel_id=channel.id,
            theme=theme.name,
            category=theme.category,
            date=day.isoformat(),
        )
        return theme

    async def record_publication(
        self,
        channel_id: int,
        theme: PostcardTheme,
        *,
        published_on: date | None = None,
    ) -> None:
        """Фиксирует публикацию темы в истории и недельной статистике."""
        day = published_on or date.today()
        history = await self._load_history(channel_id)
        history = [
            ThemeHistoryEntry(name=theme.name, category=theme.category, published_on=day),
            *history,
        ]
        await self._settings.set(
            postcard_theme_history_key(channel_id),
            serialize_theme_history(history),
        )

        week_key = iso_week_key(day)
        stored_key, counts = await self._load_week_stats(channel_id)
        if stored_key != week_key:
            counts = {}
        counts = record_category_use(self._catalog.manifest, counts, theme)
        await self._settings.set(
            postcard_week_stats_key(channel_id),
            serialize_week_stats(week_key, counts),
        )
        await self._session.commit()

    async def _load_or_build_plan(self, channel: Channel, day: date) -> DailyPlan:
        plan = await self._load_plan(channel.id)
        if plan is not None and plan.plan_date == day and plan.remaining():
            return plan
        slots_count = max(1, len(parse_publish_times(channel.publish_times)))
        history = await self._load_history(channel.id)
        week_key = iso_week_key(day)
        stored_key, week_counts = await self._load_week_stats(channel.id)
        if stored_key != week_key:
            week_counts = {}
        plan = self._selector.build_daily_plan(
            day,
            slots_count,
            history,
            week_counts,
        )
        await self._save_plan(channel.id, plan)
        return plan

    async def _load_plan(self, channel_id: int) -> DailyPlan | None:
        raw = await self._settings.get(postcard_daily_plan_key(channel_id), "")
        if not raw.strip():
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict):
            return None
        plan_date_raw = str(data.get("plan_date", "")).strip()
        try:
            plan_date = date.fromisoformat(plan_date_raw)
        except ValueError:
            return None
        slots_raw = data.get("slots", [])
        slots: list[PostcardTheme] = []
        if isinstance(slots_raw, list):
            for item in slots_raw:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                category = str(item.get("category", "")).strip()
                if name:
                    slots.append(
                        PostcardTheme(
                            name=name,
                            category=category,
                            is_holiday=bool(item.get("is_holiday", False)),
                            mandatory=bool(item.get("mandatory", False)),
                        )
                    )
        return DailyPlan(
            plan_date=plan_date,
            slots=slots,
            next_index=int(data.get("next_index", 0)),
        )

    async def _save_plan(self, channel_id: int, plan: DailyPlan) -> None:
        payload = {
            "plan_date": plan.plan_date.isoformat(),
            "next_index": plan.next_index,
            "slots": [
                {
                    "name": s.name,
                    "category": s.category,
                    "is_holiday": s.is_holiday,
                    "mandatory": s.mandatory,
                }
                for s in plan.slots
            ],
        }
        await self._settings.set(
            postcard_daily_plan_key(channel_id),
            json.dumps(payload, ensure_ascii=False),
        )
        await self._session.commit()

    async def _load_history(self, channel_id: int) -> list[ThemeHistoryEntry]:
        raw = await self._settings.get(postcard_theme_history_key(channel_id), "")
        return parse_theme_history(raw)

    async def _load_week_stats(self, channel_id: int) -> tuple[str, dict[str, int]]:
        raw = await self._settings.get(postcard_week_stats_key(channel_id), "")
        return parse_week_stats(raw)
