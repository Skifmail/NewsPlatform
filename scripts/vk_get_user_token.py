#!/usr/bin/env python3
"""
Получение VK user access token через Authorization Code flow.

Запускается ЛОКАЛЬНО (не на сервере) — открывает браузер и ловит callback.

Шаги:
  1. Добавьте redirect URI в настройках VK приложения 54690717:
       http://localhost:8765/callback
  2. Запустите скрипт:
       python scripts/vk_get_user_token.py --client_secret <ВАШ_СЕКРЕТ>
  3. Войдите в VK в открывшемся браузере и разрешите доступ.
  4. Скопируйте токен из вывода и сохраните в БД (команда будет выведена).

Права токена: photos, wall, groups, offline (не истекает).
"""

import argparse
import http.server
import json
import threading
import urllib.parse
import urllib.request
import webbrowser

CLIENT_ID = "54690770"
REDIRECT_URI = "http://localhost:8765/callback"
SCOPE = "photos,wall,groups,offline"
PORT = 8765

_result: dict = {}
_done = threading.Event()


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if "code" in params:
            _result["code"] = params["code"][0]
            body = b"<h1>OK! Code received. You can close this tab.</h1>"
            self.send_response(200)
        elif "error" in params:
            err = params.get("error", ["unknown"])[0]
            desc = params.get("error_description", [""])[0]
            _result["error"] = f"{err}: {desc}"
            body = f"<h1>Error: {err}</h1><p>{desc}</p>".encode()
            self.send_response(400)
        else:
            self.send_response(400)
            self.end_headers()
            return
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)
        _done.set()

    def log_message(self, *_args: object) -> None:
        pass


def _exchange_code(code: str, client_secret: str) -> dict:
    url = (
        "https://oauth.vk.com/access_token"
        f"?client_id={CLIENT_ID}"
        f"&client_secret={urllib.parse.quote(client_secret)}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&code={urllib.parse.quote(code)}"
    )
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def main() -> None:
    parser = argparse.ArgumentParser(description="VK OAuth — получить user token")
    parser.add_argument("--client_secret", required=True, help="Секрет приложения VK 54690770")
    args = parser.parse_args()

    auth_url = (
        "https://oauth.vk.com/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&scope={SCOPE}"
        f"&response_type=code"
        f"&v=5.199"
    )

    print("\n" + "=" * 60)
    print("VK OAuth — получение user access token")
    print("=" * 60)
    print(f"\nПриложение VK ID: {CLIENT_ID}")
    print(f"Redirect URI (добавьте в настройки приложения если не добавлен):")
    print(f"  {REDIRECT_URI}")
    print(f"\nОткрываем браузер...")

    server = http.server.HTTPServer(("localhost", PORT), _CallbackHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    webbrowser.open(auth_url)
    print(f"Ожидаем авторизацию (таймаут 120 сек)...\n")

    _done.wait(timeout=120)
    server.shutdown()

    if "error" in _result:
        print(f"\nОшибка авторизации: {_result['error']}")
        return

    if "code" not in _result:
        print("\nТаймаут — авторизация не завершена.")
        return

    print("Код получен. Обмениваем на токен...")
    try:
        data = _exchange_code(_result["code"], args.client_secret)
    except Exception as exc:
        print(f"\nОшибка при обмене кода: {exc}")
        return

    if "error" in data:
        print(f"\nОшибка VK: {data.get('error')}: {data.get('error_description')}")
        return

    token = data.get("access_token", "")
    user_id = data.get("user_id")
    expires_in = data.get("expires_in", 0)

    print("\n" + "=" * 60)
    print("Токен успешно получен!")
    print(f"VK User ID : {user_id}")
    print(f"Срок       : {'бессрочный (offline)' if expires_in == 0 else f'{expires_in} сек'}")
    print(f"\nAccess Token:\n{token}")
    print("=" * 60)
    print("\nСохраните токен в БД (выполните на сервере):")
    print(
        "  docker exec -i newsplatform-news-yzwxxs-postgres-1 \\\n"
        "    psql -U postgres content_platform -c \\\n"
        f"    \"INSERT INTO settings (key,value) VALUES ('vk_user_token','{token}')\n"
        "     ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value;\""
    )
    print()


if __name__ == "__main__":
    main()
