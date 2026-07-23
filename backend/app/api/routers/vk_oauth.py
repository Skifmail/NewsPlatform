"""VK OAuth flow — одноразовое получение user token с правами photos+wall+groups."""

import base64
import hashlib
import os
import urllib.parse

import aiohttp
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository

router = APIRouter(prefix="/vk/oauth", tags=["vk-oauth"])

_SCOPE = "photos,wall,groups,offline"
_PKCE_COOKIE = "vk_pkce_verifier"


def _callback_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    if proto == "http" and request.headers.get("x-forwarded-for"):
        proto = "https"
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{proto}://{host}/api/vk/oauth/callback"


def _pkce_pair() -> tuple[str, str]:
    """Returns (code_verifier, code_challenge) for S256 PKCE."""
    verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


@router.get("/start")
async def vk_oauth_start(request: Request) -> RedirectResponse:
    """Перенаправляет на страницу авторизации VK (Authorization Code + PKCE)."""
    settings = get_settings()
    if not settings.vk_app_client_secret:
        raise HTTPException(
            status_code=500,
            detail="VK_APP_CLIENT_SECRET не настроен — добавьте в .env и перезапустите контейнер",
        )

    verifier, challenge = _pkce_pair()
    callback = _callback_url(request)

    auth_url = (
        "https://oauth.vk.com/authorize"
        f"?client_id={settings.vk_app_client_id}"
        f"&redirect_uri={urllib.parse.quote(callback, safe='')}"
        f"&scope={_SCOPE}"
        "&response_type=code"
        f"&code_challenge={challenge}"
        "&code_challenge_method=S256"
        "&v=5.199"
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
    """Принимает code от VK, обменивает на токен и сохраняет как vk_user_token в БД."""
    if error:
        return HTMLResponse(
            f"<h2>Ошибка VK OAuth</h2><p>{error}: {error_description}</p>",
            status_code=400,
        )
    if not code:
        return HTMLResponse("<h2>Нет кода авторизации</h2>", status_code=400)

    settings = get_settings()
    verifier = request.cookies.get(_PKCE_COOKIE, "")
    callback = _callback_url(request)

    token_params: dict[str, str] = {
        "client_id": settings.vk_app_client_id,
        "client_secret": settings.vk_app_client_secret,
        "redirect_uri": callback,
        "code": code,
    }
    if verifier:
        token_params["code_verifier"] = verifier

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://oauth.vk.com/access_token", data=token_params
        ) as resp:
            data = await resp.json()

    if "error" in data:
        return HTMLResponse(
            f"<h2>Ошибка при обмене кода</h2>"
            f"<p>{data.get('error')}: {data.get('error_description')}</p>",
            status_code=400,
        )

    access_token: str = data.get("access_token", "")
    user_id = data.get("user_id")

    async with async_session_factory() as db:
        repo = SettingRepository(db)
        await repo.set("vk_user_token", access_token)
        await db.commit()

    return HTMLResponse(
        "<h2 style='color:green'>VK user token сохранён!</h2>"
        f"<p>VK User ID: {user_id}</p>"
        "<p>Токен записан в настройку <code>vk_user_token</code>.</p>"
        "<p>Следующие публикации в VK будут содержать фото.</p>"
    )
