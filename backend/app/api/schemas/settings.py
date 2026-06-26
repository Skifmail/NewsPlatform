"""Схемы настроек."""

from pydantic import BaseModel


class SettingsResponse(BaseModel):
    """Все настройки."""

    settings: dict[str, str]


class SettingsUpdate(BaseModel):
    """Обновление настроек."""

    settings: dict[str, str]
