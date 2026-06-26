"""Роутер входа в панель управления."""

import secrets

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AuthDep
from app.api.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.core.config import get_settings
from app.core.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest) -> TokenResponse:
    """Проверяет логин/пароль и выдаёт JWT.

    Args:
        data: учётные данные.

    Returns:
        TokenResponse: токен доступа.

    Raises:
        HTTPException: 401 при неверных данных.
    """
    settings = get_settings()
    user_ok = secrets.compare_digest(data.username, settings.admin_username)
    pass_ok = secrets.compare_digest(data.password, settings.admin_password)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )
    token = create_access_token(data.username)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserResponse)
async def me(username: AuthDep) -> UserResponse:
    """Возвращает текущего пользователя по токену.

    Args:
        username: логин из JWT.

    Returns:
        UserResponse: имя пользователя.
    """
    return UserResponse(username=username)
