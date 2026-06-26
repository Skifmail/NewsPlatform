"""Авторизация Telethon userbot-сессии по QR-коду.

Запускать в интерактивном терминале (с флагом ``-it``):

    docker compose exec -it celery_worker python scripts/telethon_login.py

Вход по QR не требует кода из SMS/приложения и не зависит от лимитов
``send_code``. В терминале появится QR — отсканируйте его в приложении
Telegram: Настройки → Устройства → «Подключить устройство».

Если QR не подходит, запустите с аргументом ``code`` для входа по коду:

    docker compose exec -it celery_worker python scripts/telethon_login.py code
"""

import asyncio
import sys

import qrcode
from telethon import TelegramClient
from telethon.errors import (
    PasswordHashInvalidError,
    SessionPasswordNeededError,
)
from telethon.tl.functions.account import GetPasswordRequest

from app.core.config import get_settings
from app.infrastructure.parsers.telegram_parser import SESSION_PATH


def _print_qr(data: str) -> None:
    """Рисует QR-код в терминале (ASCII).

    Args:
        data: строка ссылки для кодирования.
    """
    qr = qrcode.QRCode(border=2)
    qr.add_data(data)
    qr.make(fit=True)
    qr.print_ascii(invert=True)


async def _enter_2fa_password(client: TelegramClient) -> bool:
    """Запрашивает облачный пароль 2FA с повтором при ошибке.

    Args:
        client: подключённый клиент (QR уже отсканирован).

    Returns:
        bool: True при успешном вводе пароля.
    """
    hint = ""
    try:
        pwd_info = await client(GetPasswordRequest())
        hint = getattr(pwd_info, "hint", "") or ""
    except Exception:  # noqa: BLE001
        hint = ""

    if hint:
        print(f"Подсказка к паролю: {hint}")

    for attempt in range(1, 6):
        password = input(
            f"Введите облачный пароль 2FA (попытка {attempt}/5): "
        ).strip()
        try:
            await client.sign_in(password=password)
            return True
        except PasswordHashInvalidError:
            print("Неверный пароль. Попробуйте ещё раз.")
    print(
        "Превышено число попыток. Если забыли пароль 2FA — сбросьте его в "
        "Telegram: Настройки → Конфиденциальность → Облачный пароль."
    )
    return False


async def _login_via_qr(client: TelegramClient) -> bool:
    """Вход по QR-коду с обновлением при истечении.

    Args:
        client: подключённый клиент.

    Returns:
        bool: True при успешной авторизации.
    """
    print(
        "\nОткройте Telegram на телефоне → Настройки → Устройства → "
        "«Подключить устройство» и отсканируйте QR ниже.\n"
        "QR обновляется автоматически; держите окно открытым.\n"
    )
    try:
        qr_login = await client.qr_login()
    except SessionPasswordNeededError:
        return await _enter_2fa_password(client)

    while True:
        _print_qr(qr_login.url)
        print("Ожидание сканирования… (QR действует ~30 сек, затем обновится)")
        try:
            result = await qr_login.wait(timeout=30)
            if result:
                return True
        except asyncio.TimeoutError:
            await qr_login.recreate()
            continue
        except SessionPasswordNeededError:
            return await _enter_2fa_password(client)


async def _login_via_code(client: TelegramClient, phone: str) -> bool:
    """Резервный вход по коду подтверждения.

    Args:
        client: подключённый клиент.
        phone: номер телефона.

    Returns:
        bool: True при успешной авторизации.
    """
    await client.send_code_request(phone)
    code = input("Введите код подтверждения: ").strip()
    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        password = input("Включена 2FA. Введите облачный пароль: ").strip()
        await client.sign_in(password=password)
    return True


async def main() -> int:
    """Запускает авторизацию (по умолчанию QR, опционально по коду).

    Returns:
        int: код возврата процесса.
    """
    settings = get_settings()
    if not (settings.telegram_api_id and settings.telegram_api_hash):
        print("ERROR: TELEGRAM_API_ID / TELEGRAM_API_HASH не заданы в .env")
        return 1

    use_code = len(sys.argv) > 1 and sys.argv[1] == "code"

    client = TelegramClient(
        SESSION_PATH,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    print("Подключаюсь к Telegram…")
    await client.connect()

    if await client.is_user_authorized():
        me = await client.get_me()
        name = getattr(me, "username", None) or getattr(me, "first_name", "?")
        print(f"OK: уже авторизован как {name} (id={me.id}). Ничего делать не нужно.")
        await client.disconnect()
        return 0

    try:
        if use_code:
            if not settings.telegram_phone:
                print("ERROR: TELEGRAM_PHONE не задан в .env")
                await client.disconnect()
                return 1
            await _login_via_code(client, settings.telegram_phone)
        else:
            await _login_via_qr(client)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR при авторизации: {type(exc).__name__}: {exc}")
        await client.disconnect()
        return 1

    me = await client.get_me()
    name = getattr(me, "username", None) or getattr(me, "first_name", "?")
    print(f"\nOK: авторизован как {name} (id={me.id})")
    await client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
