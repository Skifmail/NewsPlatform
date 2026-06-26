"""Проверки флагов настроек для ручных действий API."""

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.platform_settings_service import PlatformSettingsService


async def require_manual_fetch(session: AsyncSession) -> None:
    """Запрещает ручной парсинг, если выключен в настройках.

    Args:
        session: сессия БД.

    Raises:
        HTTPException: 403 если manual_fetch_enabled = false.
    """
    ps = await PlatformSettingsService(session).load()
    if not ps.manual_fetch_enabled:
        raise HTTPException(
            status_code=403,
            detail="Ручной парсинг отключён в настройках платформы",
        )


async def require_manual_ai(session: AsyncSession) -> None:
    """Запрещает ручную AI-обработку, если выключена в настройках.

    Args:
        session: сессия БД.

    Raises:
        HTTPException: 403 если manual_ai_enabled = false.
    """
    ps = await PlatformSettingsService(session).load()
    if not ps.manual_ai_enabled:
        raise HTTPException(
            status_code=403,
            detail="Ручная AI-обработка отключена в настройках платформы",
        )


async def require_manual_publish(session: AsyncSession) -> None:
    """Запрещает ручную публикацию, если выключена в настройках.

    Args:
        session: сессия БД.

    Raises:
        HTTPException: 403 если manual_publish_enabled = false.
    """
    ps = await PlatformSettingsService(session).load()
    if not ps.manual_publish_enabled:
        raise HTTPException(
            status_code=403,
            detail="Ручная публикация отключена в настройках платформы",
        )
