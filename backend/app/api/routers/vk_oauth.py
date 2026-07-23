"""VK OAuth — получение user token через классический implicit flow."""

import urllib.parse

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository

router = APIRouter(prefix="/vk/oauth", tags=["vk-oauth"])

# oauth.vk.com/blank.html — стандартный redirect для Standalone-приложений.
# Используем client_id Kate Mobile (2685278) — standalone OAuth без direct auth.
_AUTH_URL = (
    "https://oauth.vk.com/authorize"
    "?client_id=2685278"
    "&redirect_uri=https%3A%2F%2Foauth.vk.com%2Fblank.html"
    "&scope=photos%2Cwall%2Cgroups%2Coffline"
    "&response_type=token"
    "&display=mobile"
    "&revoke=1"
)


@router.get("/start")
async def vk_oauth_start() -> HTMLResponse:
    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>VK User Token</title>
  <style>
    body{{font-family:sans-serif;max-width:560px;margin:40px auto;padding:0 16px}}
    h2{{color:#222}}
    .btn{{background:#2787f5;color:#fff;padding:12px 24px;border:none;border-radius:6px;
          font-size:15px;cursor:pointer;text-decoration:none;display:inline-block}}
    .btn:hover{{background:#1a6fc4}}
    .btn-green{{background:#4caf50}}.btn-green:hover{{background:#388e3c}}
    .step{{background:#f5f5f5;border-radius:8px;padding:16px;margin:16px 0}}
    textarea{{width:100%;height:64px;font-family:monospace;font-size:12px;
              box-sizing:border-box;padding:8px;margin:8px 0;border:1px solid #ccc;border-radius:4px}}
    code{{background:#e0e0e0;padding:2px 5px;border-radius:3px;font-size:12px;word-break:break-all}}
    #result{{margin-top:10px;font-weight:bold}}
  </style>
</head>
<body>
  <h2>Получение VK User Token</h2>

  <div class="step">
    <b>Шаг 1.</b> Нажмите кнопку и войдите в ВКонтакте:<br><br>
    <a class="btn" href="{_AUTH_URL}" target="_blank">Авторизоваться в VK →</a>
  </div>

  <div class="step">
    <b>Шаг 2.</b> После нажатия «Разрешить» VK откроет пустую страницу.<br>
    Скопируйте <b>весь</b> адрес из строки браузера — он выглядит так:<br><br>
    <code>https://oauth.vk.com/blank.html#access_token=<b>ВОТ_ЭТО_НУЖНО</b>&amp;expires_in=0&amp;user_id=...</code><br><br>
    Скопируйте только значение после <code>access_token=</code> и до <code>&amp;</code>.
  </div>

  <div class="step">
    <b>Шаг 3.</b> Вставьте токен и нажмите «Сохранить»:<br>
    <textarea id="t" placeholder="Вставьте access_token (начинается с vk1.a. или длинная строка)..."></textarea>
    <button class="btn btn-green" onclick="save()">Сохранить токен</button>
    <div id="result"></div>
  </div>

  <script>
    async function save() {{
      const raw = document.getElementById('t').value.trim();
      // Если вставили весь URL — извлечём токен автоматически
      let token = raw;
      const m = raw.match(/[?#&]access_token=([^&]+)/);
      if (m) token = m[1];
      if (!token) {{
        document.getElementById('result').innerHTML = '<span style="color:red">Токен пустой</span>';
        return;
      }}
      const r = await fetch('/api/vk/oauth/save', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{token}})
      }});
      document.getElementById('result').innerHTML = await r.text();
    }}
  </script>
</body>
</html>""")


class _TokenBody(BaseModel):
    token: str


@router.post("/save")
async def vk_oauth_save(body: _TokenBody) -> HTMLResponse:
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
        "<span style='color:green;font-size:16px'>&#10003; Токен сохранён! "
        "Следующие публикации в VK будут содержать фото.</span>"
    )
