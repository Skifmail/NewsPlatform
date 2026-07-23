"""VK OAuth — Authorization Code + PKCE для Web-приложения (id.vk.ru)."""

import base64
import hashlib
import secrets
import urllib.parse

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository

router = APIRouter(prefix="/vk/oauth", tags=["vk-oauth"])

_SCOPE = "photos wall groups offline"
_CALLBACK_URL = "https://news-platform.online/api/vk/oauth/callback"
_VK_AUTH_URL = "https://oauth.vk.ru/authorize"
_VK_TOKEN_URL = "https://oauth.vk.ru/access_token"
_VERIFIER_PREFIX = "vk_oauth_verifier_"


def _make_verifier() -> str:
    return secrets.token_urlsafe(64)


def _make_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


@router.get("/start")
async def vk_oauth_start() -> RedirectResponse:
    settings = get_settings()
    verifier = _make_verifier()
    challenge = _make_challenge(verifier)
    state = secrets.token_urlsafe(16)

    async with async_session_factory() as db:
        repo = SettingRepository(db)
        await repo.set(_VERIFIER_PREFIX + state, verifier)
        await db.commit()

    params = urllib.parse.urlencode({
        "client_id": settings.vk_app_client_id,
        "redirect_uri": _CALLBACK_URL,
        "scope": _SCOPE,
        "response_type": "code",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "s256",
    })
    return RedirectResponse(f"{_VK_AUTH_URL}?{params}")


@router.get("/callback")
async def vk_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
) -> HTMLResponse:
    if error:
        return HTMLResponse(
            f"<h2>Ошибка VK OAuth</h2><p>{error}: {error_description}</p>"
            f"<p><a href='/api/vk/oauth/start'>Попробовать снова</a></p>",
            status_code=400,
        )
    if not code or not state:
        return HTMLResponse(
            "<h2>Ошибка: нет code или state в ответе VK</h2>"
            "<p><a href='/api/vk/oauth/start'>Попробовать снова</a></p>",
            status_code=400,
        )

    async with async_session_factory() as db:
        repo = SettingRepository(db)
        verifier_key = _VERIFIER_PREFIX + state
        verifier = await repo.get(verifier_key, "")
        if verifier:
            await repo.set(verifier_key, "")
        await db.commit()

    if not verifier:
        return HTMLResponse(
            "<h2>Сессия OAuth истекла или state неверный</h2>"
            "<p><a href='/api/vk/oauth/start'>Начать снова</a></p>",
            status_code=400,
        )

    settings = get_settings()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _VK_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "client_id": settings.vk_app_client_id,
                "client_secret": settings.vk_app_client_secret,
                "code": code,
                "code_verifier": verifier,
                "redirect_uri": _CALLBACK_URL,
            },
        )

    data = resp.json()
    token = data.get("access_token")

    if not token:
        err = data.get("error_description") or data.get("error") or str(data)
        return HTMLResponse(
            f"<h2>Не удалось получить токен</h2><p>{err}</p>"
            f"<p>Ответ VK: <code>{data}</code></p>"
            f"<p><a href='/api/vk/oauth/start'>Попробовать снова</a></p>",
            status_code=400,
        )

    async with async_session_factory() as db:
        repo = SettingRepository(db)
        await repo.set("vk_user_token", token)
        await db.commit()

    user_id = data.get("user_id", "")
    return HTMLResponse(
        "<!DOCTYPE html><html><body style='font-family:sans-serif;"
        "max-width:500px;margin:60px auto;text-align:center'>"
        "<h2 style='color:green'>&#10003; VK user token сохранён!</h2>"
        + (f"<p>VK User ID: {user_id}</p>" if user_id else "")
        + "<p>Следующие публикации в VK будут содержать фото.</p>"
        "</body></html>"
    )
