"""JWT-токены для панели управления."""

from datetime import UTC, datetime, timedelta

import jwt
from jwt.exceptions import InvalidTokenError

from app.core.config import get_settings

ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 24


def create_access_token(username: str) -> str:
    """Создаёт JWT для авторизованного пользователя.

    Args:
        username: логин панели.

    Returns:
        str: подписанный JWT.
    """
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Проверяет JWT и возвращает логин.

    Args:
        token: строка Bearer-токена.

    Returns:
        str | None: логин или None при невалидном токене.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except InvalidTokenError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None
