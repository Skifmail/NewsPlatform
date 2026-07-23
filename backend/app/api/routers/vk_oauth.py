"""VK OAuth flow — получение user token с правами photos+wall+groups+offline."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.core.config import get_settings
from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository

router = APIRouter(prefix="/vk/oauth", tags=["vk-oauth"])

_SCOPE = "photos,wall,groups,offline"


@router.get("/start")
async def vk_oauth_start() -> HTMLResponse:
    """Страница для получения VK user token через implicit flow."""
    settings = get_settings()
    auth_url = (
        "https://oauth.vk.com/authorize"
        f"?client_id={settings.vk_app_client_id}"
        "&redirect_uri=https%3A%2F%2Foauth.vk.com%2Fblank.html"
        f"&scope={_SCOPE}"
        "&response_type=token"
        "&v=5.199"
    )
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>VK OAuth</title>
  <style>
    body {{ font-family: sans-serif; max-width: 620px; margin: 40px auto; padding: 0 20px; }}
    .btn {{ background: #2787f5; color: #fff; border: none; padding: 12px 24px;
             font-size: 16px; border-radius: 6px; cursor: pointer;
             text-decoration: none; display: inline-block; }}
    .btn:hover {{ background: #1a6fc4; }}
    textarea {{ width: 100%; height: 80px; font-family: monospace; font-size: 13px;
                margin: 8px 0; box-sizing: border-box; }}
    .step {{ margin: 20px 0; padding: 16px; background: #f5f5f5; border-radius: 8px; }}
    code {{ background: #e0e0e0; padding: 2px 4px; border-radius: 3px; }}
    .note {{ color: #555; font-size: 13px; margin-top: 8px; }}
    #result {{ margin-top: 12px; font-weight: bold; }}
  </style>
</head>
<body>
  <h2>Получение VK User Token</h2>
  <div class="step">
    <b>Шаг 1.</b> Нажмите кнопку — откроется авторизация VK в новой вкладке.<br><br>
    <a class="btn" href="{auth_url}" target="_blank">Авторизоваться в VK</a>
  </div>
  <div class="step">
    <b>Шаг 2.</b> После разрешения доступа VK перенаправит на белую страницу.<br>
    Скопируйте значение <code>access_token</code> из адресной строки.<br>
    <div class="note">URL будет выглядеть так:<br>
    <code>https://oauth.vk.com/blank.html#access_token=<b>СЮДА_СКОПИРОВАТЬ</b>&amp;expires_in=0&amp;user_id=...</code></div>
  </div>
  <div class="step">
    <b>Шаг 3.</b> Вставьте токен и нажмите «Сохранить»:
    <br>
    <textarea id="tokenInput" placeholder="Вставьте access_token сюда..."></textarea><br>
    <button class="btn" onclick="saveToken()">Сохранить токен</button>
    <div id="result"></div>
  </div>
  <script>
    async function saveToken() {{
      const token = document.getElementById('tokenInput').value.trim();
      if (!token) {{ document.getElementById('result').innerHTML = '<span style="color:red">Токен пустой</span>'; return; }}
      const res = await fetch('/api/vk/oauth/save', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{token}})
      }});
      const text = await res.text();
      document.getElementById('result').innerHTML = text;
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
        return HTMLResponse("<span style='color:red'>Токен не может быть пустым</span>", status_code=400)

    async with async_session_factory() as db:
        repo = SettingRepository(db)
        await repo.set("vk_user_token", token)
        await db.commit()

    return HTMLResponse(
        "<span style='color:green'>&#10003; VK user token сохранён!</span> "
        "Следующие публикации в VK будут содержать фото."
    )
