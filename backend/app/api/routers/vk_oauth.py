"""VK OAuth — получение user token (поддерживает oauth.vk.ru и oauth.vk.com)."""

import urllib.parse

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository

router = APIRouter(prefix="/vk/oauth", tags=["vk-oauth"])

_SCOPE = "photos,wall,groups,offline"
_CALLBACK_URL = "https://news-platform.online/api/vk/oauth/callback"


@router.get("/start")
async def vk_oauth_start() -> RedirectResponse:
    """Implicit flow через oauth.vk.ru с нашим зарегистрированным redirect URI."""
    settings = get_settings()
    auth_url = (
        "https://oauth.vk.ru/authorize"
        f"?client_id={settings.vk_app_client_id}"
        f"&redirect_uri={urllib.parse.quote(_CALLBACK_URL, safe='')}"
        f"&scope={_SCOPE}"
        "&response_type=token"
        "&display=page"
        "&v=5.199"
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
async def vk_oauth_callback(
    error: str | None = None,
    error_description: str | None = None,
) -> HTMLResponse:
    """Извлекает токен из URL-фрагмента через JS и сохраняет в БД."""
    if error:
        return HTMLResponse(
            f"<h2>Ошибка VK OAuth</h2><p>{error}: {error_description}</p>",
            status_code=400,
        )
    return HTMLResponse("""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>VK OAuth</title>
  <style>body{font-family:sans-serif;max-width:500px;margin:60px auto;text-align:center}</style>
</head>
<body>
  <h2 id="title">Сохраняем токен...</h2>
  <div id="msg"></div>
  <script>
    const hash = window.location.hash.slice(1);
    const params = new URLSearchParams(hash);
    const token = params.get('access_token');
    const userId = params.get('user_id');
    if (!token) {
      document.getElementById('title').textContent = 'Ошибка';
      document.getElementById('msg').innerHTML =
        '<p style="color:red">access_token не найден в URL</p>'
        + '<p><a href="/api/vk/oauth/start">Попробовать снова</a></p>';
    } else {
      fetch('/api/vk/oauth/save', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({token})
      })
      .then(r => r.text())
      .then(html => {
        document.getElementById('title').textContent = '';
        document.getElementById('msg').innerHTML = html
          + (userId ? '<p>VK User ID: ' + userId + '</p>' : '');
      })
      .catch(e => {
        document.getElementById('title').textContent = 'Ошибка сохранения';
        document.getElementById('msg').innerHTML = '<span style="color:red">' + e + '</span>';
      });
    }
  </script>
</body>
</html>""")


class _TokenBody(BaseModel):
    token: str


@router.post("/save")
async def vk_oauth_save(body: _TokenBody) -> HTMLResponse:
    """Сохраняет vk_user_token в БД."""
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
        "<span style='color:green'>&#10003; Токен сохранён! "
        "Следующие публикации в VK будут содержать фото.</span>"
    )
