"""VK OAuth flow через id.vk.com (для приложений VK ID)."""

import base64
import hashlib
import os
import urllib.parse

import aiohttp
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository

router = APIRouter(prefix="/vk/oauth", tags=["vk-oauth"])

# Пространство-разделённые скоупы для id.vk.com/oauth2
_SCOPE = "photos wall groups offline"
_CALLBACK_URL = "https://news-platform.online/api/vk/oauth/callback"
_PKCE_COOKIE = "vk_pkce_verifier"


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@router.get("/start")
async def vk_oauth_start() -> RedirectResponse:
    """Перенаправляет на id.vk.com (Authorization Code + PKCE — обязателен для VK ID apps)."""
    settings = get_settings()
    verifier, challenge = _pkce_pair()

    auth_url = (
        "https://id.vk.com/oauth2/auth"
        f"?client_id={settings.vk_app_client_id}"
        f"&redirect_uri={urllib.parse.quote(_CALLBACK_URL, safe='')}"
        f"&scope={urllib.parse.quote(_SCOPE, safe='')}"
        "&response_type=code"
        f"&code_challenge={challenge}"
        "&code_challenge_method=S256"
    )
    response = RedirectResponse(auth_url)
    response.set_cookie(_PKCE_COOKIE, verifier, max_age=600, httponly=True, samesite="lax")
    return response


@router.get("/callback")
async def vk_oauth_callback(
    request: Request,
    code: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> HTMLResponse:
    """Принимает code, обменивает на токен через id.vk.com и сохраняет в БД."""
    if error:
        return HTMLResponse(
            f"<h2>Ошибка VK OAuth</h2><p>{error}: {error_description}</p>",
            status_code=400,
        )
    if not code:
        return HTMLResponse("<h2>Нет кода авторизации</h2>", status_code=400)

    settings = get_settings()
    verifier = request.cookies.get(_PKCE_COOKIE, "")

    token_params: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": settings.vk_app_client_id,
        "client_secret": settings.vk_app_client_secret,
        "redirect_uri": _CALLBACK_URL,
    }
    if verifier:
        token_params["code_verifier"] = verifier

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://id.vk.com/oauth2/token", data=token_params
        ) as resp:
            data = await resp.json(content_type=None)

    if "error" in data:
        return HTMLResponse(
            f"<h2>Ошибка при обмене кода</h2>"
            f"<p>{data.get('error')}: {data.get('error_description')}</p>"
            f"<pre>{data}</pre>",
            status_code=400,
        )

    access_token: str = data.get("access_token", "")
    user_id = data.get("user_id")

    async with async_session_factory() as db:
        repo = SettingRepository(db)
        await repo.set("vk_user_token", access_token)
        await db.commit()

    return HTMLResponse(
        "<h2 style='color:green'>&#10003; VK user token сохранён!</h2>"
        f"<p>VK User ID: {user_id}</p>"
        "<p>Следующие публикации в VK будут содержать фото.</p>"
    )


class _TokenBody(BaseModel):
    token: str


@router.post("/save")
async def vk_oauth_save(body: _TokenBody) -> HTMLResponse:
    """Ручное сохранение токена (резервный вариант)."""
    token = body.token.strip()
    if not token:
        return HTMLResponse(
            "<span style='color:red'>Токен не может быть пустым</span>",
            status_code=400,
        )
    async with async_session_factory() as db:
        repo = SettingRepository(db)
        await repo.set("vk_user_token", token)
        await db.commit()
    return HTMLResponse(
        "<h2 style='color:green'>&#10003; VK user token сохранён!</h2>"
        "<p>Следующие публикации в VK будут содержать фото.</p>"
    )
