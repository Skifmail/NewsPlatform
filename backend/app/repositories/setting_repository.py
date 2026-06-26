"""Репозиторий настроек."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.setting import Setting


class SettingRepository:
    """CRUD для settings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> dict[str, str]:
        """Все настройки как словарь.

        Returns:
            dict[str, str]: key -> value.
        """
        result = await self._session.execute(select(Setting))
        return {s.key: s.value for s in result.scalars().all()}

    async def get(self, key: str, default: str = "") -> str:
        """Значение настройки.

        Args:
            key: ключ.
            default: значение по умолчанию.

        Returns:
            str: значение.
        """
        setting = await self._session.get(Setting, key)
        return setting.value if setting else default

    async def set(self, key: str, value: str) -> None:
        """Устанавливает настройку.

        Args:
            key: ключ.
            value: значение.
        """
        setting = await self._session.get(Setting, key)
        if setting:
            setting.value = value
        else:
            self._session.add(Setting(key=key, value=value))
        await self._session.flush()

    async def update_many(self, data: dict[str, str]) -> None:
        """Обновляет несколько настроек.

        Args:
            data: словарь key -> value.
        """
        for key, value in data.items():
            await self.set(key, value)
