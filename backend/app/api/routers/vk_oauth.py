"""VK OAuth flow — одноразовое получение user token с правами photos+wall+groups."""

import urllib.parse

import aiohttp
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository

router = APIRouter(prefix="/vk/oauth", tags=["vk-oauth"])

_SCOPE = "photos,wall,groups,offline"


def _callback_url(request: Request) -> str:
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.url.netloc)
    return f"{proto}://{host}/api/vk/oauth/callback"


@router.get("/start")
async def vk_oauth_start(request: Request) -> RedirectResponse:
    """Перенаправляет на страницу авторизации VK."""
    settings = get_settings()
    if not settings.vk_app_client_secret:
        raise HTTPException(
            status_code=500,
            detail="VK_APP_CLIENT_SECRET не настроен — добавьте в .env и перезапустите контейнер",
        )

    auth_url = (
        "https://oauth.vk.com/authorize"
        f"?client_id={settings.vk_app_client_id}"
        f"&redirect_uri={urllib.parse.quote(_callback_url(request))}"
        f"&scope={_SCOPE}"
        "&response_type=code"
        "&v=5.199"
    )
    return RedirectResponse(auth_url)


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
    token_url = (
        "https://oauth.vk.com/access_token"
        f"?client_id={settings.vk_app_client_id}"
        f"&client_secret={urllib.parse.quote(settings.vk_app_client_secret)}"
        f"&redirect_uri={urllib.parse.quote(_callback_url(request))}"
        f"&code={urllib.parse.quote(code)}"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(token_url) as resp:
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
