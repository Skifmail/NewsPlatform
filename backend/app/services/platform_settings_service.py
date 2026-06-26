"""Загрузка и обновление настроек платформы из БД."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.curated_pick import (
    CURATED_PICK_HISTORY_KEY,
    CURATED_PICK_HISTORY_LIMIT,
    CuratedPickRecord,
    parse_curated_pick_history,
    serialize_curated_pick_history,
)
from app.domain.platform_settings import (
    PLATFORM_SETTINGS_DEFAULTS,
    PlatformSettings,
    curated_scheduler_key,
    is_internal_setting_key,
)
from app.repositories.setting_repository import SettingRepository


class PlatformSettingsService:
    """Чтение настроек с дефолтами и служебными метками планировщика."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = SettingRepository(session)

    async def get_merged(self) -> dict[str, str]:
        """Все настройки: дефолты, перекрытые значениями из БД.

        Returns:
            dict[str, str]: полный словарь для API и задач.
        """
        stored = await self._repo.get_all()
        return {**PLATFORM_SETTINGS_DEFAULTS, **stored}

    async def get_public_merged(self) -> dict[str, str]:
        """Настройки для панели без служебных ключей планировщика.

        Returns:
            dict[str, str]: словарь для GET /settings.
        """
        merged = await self.get_merged()
        return {
            key: value
            for key, value in merged.items()
            if not is_internal_setting_key(key)
        }

    async def load(self) -> PlatformSettings:
        """Типизированный снимок настроек.

        Returns:
            PlatformSettings: для Celery и сервисов.
        """
        return PlatformSettings.from_merged(await self.get_merged())

    async def mark_fetch_run(self, at: datetime | None = None) -> None:
        """Фиксирует время последнего автопарсинга.

        Args:
            at: момент запуска (UTC); по умолчанию — сейчас.
        """
        moment = at or datetime.now(UTC)
        await self._repo.set("scheduler_last_fetch_at", moment.isoformat())

    async def mark_retention_run(self, day_iso: str | None = None) -> None:
        """Фиксирует дату последней очистки (UTC).

        Args:
            day_iso: YYYY-MM-DD; по умолчанию — сегодня UTC.
        """
        if day_iso is None:
            day_iso = datetime.now(UTC).date().isoformat()
        await self._repo.set("scheduler_last_retention_at", day_iso)

    async def mark_analytics_run(self, at: datetime | None = None) -> None:
        """Фиксирует время последнего сбора аналитики.

        Args:
            at: момент UTC; по умолчанию — сейчас.
        """
        moment = at or datetime.now(UTC)
        await self._repo.set("scheduler_last_analytics_at", moment.isoformat())

    async def mark_curated_run(self, topic: str, at: datetime | None = None) -> None:
        """Фиксирует время последнего curated-запуска для темы.

        Args:
            topic: it | auto | russia.
            at: момент UTC; по умолчанию — сейчас.
        """
        moment = at or datetime.now(UTC)
        await self._repo.set(curated_scheduler_key(topic), moment.isoformat())

    async def record_curated_pick(self, record: CuratedPickRecord) -> None:
        """Добавляет запись в журнал выборов умной публикации.

        Args:
            record: выбранный материал и обоснование для панели.
        """
        raw = await self._repo.get(CURATED_PICK_HISTORY_KEY, "[]")
        history = parse_curated_pick_history(raw)
        history.insert(0, record)
        trimmed = history[:CURATED_PICK_HISTORY_LIMIT]
        await self._repo.set(
            CURATED_PICK_HISTORY_KEY,
            serialize_curated_pick_history(trimmed),
        )
