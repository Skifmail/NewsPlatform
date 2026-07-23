"""Резолв VK access-токена: сначала БД (settings), затем переменная окружения.

Хранение в БД (ключ ``vk_access_token``) позволяет задать/сменить токен через
psql или панель без передеплоя — как у ключей Tavily.

Для загрузки фото требуется пользовательский токен (``vk_user_token``) с правами
photos+wall+groups. Групповые (community) токены не поддерживают photos API (ошибка 27).
"""

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository

_VK_TOKEN_KEY = "vk_access_token"
_VK_USER_TOKEN_KEY = "vk_user_token"


async def resolve_vk_token() -> str:
    """Возвращает VK-токен из БД или из env.

    Returns:
        str: токен (пустая строка, если нигде не задан).
    """
    try:
        async with async_session_factory() as session:
            db_value = (await SettingRepository(session).get(_VK_TOKEN_KEY, "")).strip()
    except Exception:  # noqa: BLE001 — БД недоступна → падаем на env
        db_value = ""
    return db_value or get_settings().vk_access_token.strip()


async def resolve_vk_user_token() -> str:
    """Возвращает пользовательский VK-токен для загрузки фото.

    Порядок приоритетов: БД (ключ ``vk_user_token``) → env VK_USER_TOKEN.
    Если не задан — возвращает пустую строку.

    Returns:
        str: токен (пустая строка, если нигде не задан).
    """
    try:
        async with async_session_factory() as session:
            db_value = (
                await SettingRepository(session).get(_VK_USER_TOKEN_KEY, "")
            ).strip()
    except Exception:  # noqa: BLE001 — БД недоступна → падаем на env
        db_value = ""
    return db_value or get_settings().vk_user_token.strip()
