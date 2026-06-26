"""Схемы авторизации панели."""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Запрос входа в панель."""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    """Ответ с токеном после входа."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Текущий пользователь панели."""

    username: str
