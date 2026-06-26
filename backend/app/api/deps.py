"""FastAPI dependencies."""

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.infrastructure.database import get_db_session


async def verify_token(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Проверяет JWT в заголовке Authorization: Bearer.

    Args:
        authorization: заголовок Authorization.

    Returns:
        str: логин из токена.

    Raises:
        HTTPException: 401 при отсутствии или невалидном токене.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется авторизация",
        )
    token = authorization.removeprefix("Bearer ").strip()
    username = decode_access_token(token)
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла, войдите снова",
        )
    return username


DbSession = Annotated[AsyncSession, Depends(get_db_session)]
AuthDep = Annotated[str, Depends(verify_token)]
