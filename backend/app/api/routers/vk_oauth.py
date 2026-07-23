"""VK OAuth — ручное получение user token через Standalone-приложение VK."""

import aiohttp
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository

router = APIRouter(prefix="/vk/oauth", tags=["vk-oauth"])

_SCOPE = "photos,wall,groups,offline"


@router.get("/start")
async def vk_oauth_start() -> HTMLResponse:
    """Страница-инструкция для получения VK user token через Standalone-приложение."""
    settings = get_settings()
    client_id = settings.vk_app_client_id

    # URL для Standalone-приложения (blank.html — стандартный redirect для desktop/standalone)
    auth_url = (
        f"https://oauth.vk.com/authorize?client_id={client_id}"
        "&redirect_uri=https%3A%2F%2Foauth.vk.com%2Fblank.html"
        f"&scope={_SCOPE}"
        "&response_type=token"
        "&display=page"
        "&v=5.199"
    )

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>VK User Token</title>
  <style>
    body {{ font-family: sans-serif; max-width: 680px; margin: 40px auto; padding: 0 20px; }}
    .btn {{ background: #2787f5; color: #fff; border: none; padding: 12px 24px;
             font-size: 15px; border-radius: 6px; cursor: pointer;
             text-decoration: none; display: inline-block; margin-top: 8px; }}
    .btn:hover {{ background: #1a6fc4; }}
    .btn-green {{ background: #4caf50; }}
    .btn-green:hover {{ background: #388e3c; }}
    textarea {{ width: 100%; height: 70px; font-family: monospace; font-size: 12px;
                margin: 8px 0; box-sizing: border-box; padding: 8px; }}
    .step {{ margin: 18px 0; padding: 16px; background: #f5f5f5; border-radius: 8px; }}
    code {{ background: #ddd; padding: 2px 5px; border-radius: 3px; font-size: 13px; }}
    .warn {{ background: #fff3cd; border-left: 4px solid #ff9800; padding: 12px 16px;
              border-radius: 4px; margin: 12px 0; font-size: 14px; }}
    #result {{ margin-top: 10px; font-weight: bold; }}
  </style>
</head>
<body>
  <h2>Получение VK User Token</h2>

  <div class="warn">
    ⚠️ Приложение <b>{client_id}</b> зарегистрировано на id.vk.com и не поддерживает
    стандартный OAuth. Нужно создать <b>Standalone-приложение</b> на vk.com/apps.
  </div>

  <div class="step">
    <b>Шаг 1.</b> Создайте Standalone-приложение VK (занимает 2 минуты):<br><br>
    <a class="btn" href="https://vk.com/editapp?act=create" target="_blank">
      Создать приложение на VK
    </a><br><br>
    Выберите тип <b>«Standalone-приложение»</b>, введите любое название и нажмите «Подключить».<br>
    Скопируйте <b>ID приложения</b> из настроек.
  </div>

  <div class="step">
    <b>Шаг 2.</b> Введите ID нового Standalone-приложения и нажмите кнопку:<br><br>
    <input id="appId" type="text" placeholder="App ID (например 12345678)"
           style="padding:8px;font-size:15px;width:220px;border:1px solid #ccc;border-radius:4px">
    <button class="btn" onclick="openAuth()">Авторизоваться в VK →</button>
  </div>

  <div class="step">
    <b>Шаг 3.</b> После авторизации VK перенаправит на белую страницу.<br>
    Скопируйте значение <code>access_token</code> из адресной строки:<br>
    <small style="color:#555">https://oauth.vk.com/blank.html#access_token=<b>СКОПИРОВАТЬ_ЭТО</b>&amp;expires_in=0...</small>
  </div>

  <div class="step">
    <b>Шаг 4.</b> Вставьте токен и нажмите «Сохранить»:<br>
    <textarea id="tokenInput" placeholder="Вставьте access_token сюда..."></textarea>
    <button class="btn btn-green" onclick="saveToken()">Сохранить токен</button>
    <div id="result"></div>
  </div>

  <script>
    function openAuth() {{
      const id = document.getElementById('appId').value.trim();
      if (!id) {{ alert('Введите App ID'); return; }}
      const url = 'https://oauth.vk.com/authorize?client_id=' + id
        + '&redirect_uri=https%3A%2F%2Foauth.vk.com%2Fblank.html'
        + '&scope=photos,wall,groups,offline&response_type=token&display=page&v=5.199';
      window.open(url, '_blank');
    }}

    async function saveToken() {{
      const token = document.getElementById('tokenInput').value.trim();
      if (!token) {{ document.getElementById('result').innerHTML = '<span style="color:red">Токен пустой</span>'; return; }}
      const res = await fetch('/api/vk/oauth/save', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{token}})
      }});
      document.getElementById('result').innerHTML = await res.text();
    }}
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
