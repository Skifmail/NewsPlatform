#!/usr/bin/env python3
"""Утилита: проверка токена MAX и получение chat_id канала."""

from __future__ import annotations

import argparse
import asyncio
import sys

from app.core.config import get_settings
from app.domain.publish import PublishPermanentError
from app.infrastructure.publishers.max_publisher import MaxPublisher
from app.utils.max_api import get_max_api_base, max_client_session


async def _fetch_me(token: str) -> dict[str, object]:
    """Возвращает профиль бота (/me).

    Args:
        token: токен MAX Bot API.

    Returns:
        dict[str, object]: JSON ответа.

    Raises:
        RuntimeError: при ошибке API.
    """
    async with max_client_session() as session:
        async with session.get(
            f"{get_max_api_base()}/me",
            headers=MaxPublisher._auth_headers(token),
        ) as resp:
            payload = await resp.json(content_type=None)
            if resp.status >= 400 or not isinstance(payload, dict):
                msg = f"GET /me failed: HTTP {resp.status} {payload}"
                raise RuntimeError(msg)
            return payload


async def _resolve_chat(token: str, platform_id: str) -> int:
    """Резолвит chat_id канала.

    Args:
        token: токен бота.
        platform_id: числовой chat_id или slug/ссылка канала.

    Returns:
        int: chat_id.
    """
    async with max_client_session() as session:
        return await MaxPublisher._resolve_chat_id(session, token, platform_id)


async def _verify_chat_id(token: str, chat_id: int) -> dict[str, object]:
    """Проверяет доступ бота к каналу по числовому chat_id.

    Args:
        token: токен бота.
        chat_id: ID канала.

    Returns:
        dict[str, object]: информация о чате из GET /chats/{chatId}.

    Raises:
        RuntimeError: при ошибке API.
    """
    async with max_client_session() as session:
        async with session.get(
            f"{get_max_api_base()}/chats/{chat_id}",
            headers=MaxPublisher._auth_headers(token),
        ) as resp:
            payload = await resp.json(content_type=None)
            if resp.status >= 400 or not isinstance(payload, dict):
                msg = f"GET /chats/{chat_id} failed: HTTP {resp.status} {payload}"
                raise RuntimeError(msg)
            return payload


async def _wait_bot_added(
    token: str, *, timeout_sec: int, bot_username: str
) -> int:
    """Ждёт событие bot_added после добавления бота в канал.

    Args:
        token: токен бота.
        timeout_sec: сколько секунд опрашивать API.
        bot_username: username бота для подсказки пользователю.

    Returns:
        int: chat_id канала из события.

    Raises:
        RuntimeError: если событие не пришло за отведённое время.
    """
    deadline = asyncio.get_running_loop().time() + timeout_sec
    marker: int | None = None
    print(
        f"Ожидаю событие bot_added ({timeout_sec} с)…\n"
        f"Сейчас добавьте бота @{bot_username} в канал как администратора."
    )

    async with max_client_session() as session:
        while asyncio.get_running_loop().time() < deadline:
            params: dict[str, str | int] = {
                "limit": 100,
                "timeout": min(30, max(1, int(deadline - asyncio.get_running_loop().time()))),
                "types": "bot_added",
            }
            if marker is not None:
                params["marker"] = marker

            async with session.get(
                f"{get_max_api_base()}/updates",
                headers=MaxPublisher._auth_headers(token),
                params=params,
            ) as resp:
                payload = await resp.json(content_type=None)
                if resp.status >= 400 or not isinstance(payload, dict):
                    msg = f"GET /updates failed: HTTP {resp.status} {payload}"
                    raise RuntimeError(msg)

            next_marker = payload.get("marker")
            if isinstance(next_marker, int):
                marker = next_marker

            updates = payload.get("updates")
            if isinstance(updates, list):
                for update in updates:
                    if not isinstance(update, dict):
                        continue
                    if update.get("update_type") != "bot_added":
                        continue
                    chat_id = update.get("chat_id")
                    if chat_id is not None:
                        return int(chat_id)

    msg = (
        "Событие bot_added не получено. Добавьте бота админом в канал и повторите:\n"
        "  python scripts/max_resolve_chat.py --wait-bot-added"
    )
    raise RuntimeError(msg)


def _print_chat_not_found_help(link: str) -> None:
    """Печатает подсказки, если slug канала не найден.

    Args:
        link: нормализованный slug.
    """
    print(
        f"\nКанал с публичной ссылкой «{link}» не найден в MAX API.\n"
        "Возможные причины:\n"
        "  • канал приватный — slug max.ru/... не работает, нужен числовой chat_id;\n"
        "  • slug в URL не совпадает с публичной ссылкой канала;\n"
        "  • бот ещё не добавлен в канал.\n\n"
        "Как получить chat_id:\n"
        "  1. Откройте канал в web.max.ru — число в адресной строке это chat_id.\n"
        "  2. Или добавьте бота админом и выполните:\n"
        "       python scripts/max_resolve_chat.py --wait-bot-added\n"
        "  3. Или проверьте числовой id:\n"
        "       python scripts/max_resolve_chat.py -1234567890123456",
        file=sys.stderr,
    )


async def _run(platform_id: str | None, *, wait_bot_added: bool, wait_timeout: int) -> None:
    """Выполняет CLI-сценарий.

    Args:
        platform_id: необязательный идентификатор канала.
        wait_bot_added: ждать событие bot_added.
        wait_timeout: таймаут ожидания в секундах.
    """
    settings = get_settings()
    token = settings.max_bot_token.strip()
    if not token:
        print("MAX_BOT_TOKEN не задан в .env", file=sys.stderr)
        raise SystemExit(1)

    me = await _fetch_me(token)
    username = me.get("username", "?")
    name = me.get("name", "?")
    print(f"Бот: {name} (@{username})")

    if wait_bot_added:
        chat_id = await _wait_bot_added(
            token, timeout_sec=wait_timeout, bot_username=str(username)
        )
        info = await _verify_chat_id(token, chat_id)
        title = info.get("title", "?")
        status = info.get("status", "?")
        print(f"\nchat_id: {chat_id}")
        print(f"Канал: {title} (status={status})")
        print("\nВ панели каналов укажите platform_id:", chat_id)
        return

    if not platform_id:
        print(
            "\nПримеры:\n"
            "  python scripts/max_resolve_chat.py -1234567890123456\n"
            "  python scripts/max_resolve_chat.py my_public_channel\n"
            "  python scripts/max_resolve_chat.py --wait-bot-added"
        )
        return

    try:
        chat_id = await _resolve_chat(token, platform_id)
    except PublishPermanentError as exc:
        link = MaxPublisher._normalize_chat_link(platform_id)
        _print_chat_not_found_help(link)
        raise SystemExit(1) from exc

    info = await _verify_chat_id(token, chat_id)
    title = info.get("title", "?")
    status = info.get("status", "?")
    print(f"chat_id для «{platform_id}»: {chat_id}")
    print(f"Канал: {title} (status={status})")
    print("\nВ панели каналов укажите platform_id:", chat_id)


def main() -> None:
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        description="Проверка MAX_BOT_TOKEN и получение chat_id канала",
    )
    parser.add_argument(
        "platform_id",
        nargs="?",
        help="chat_id, @slug или ссылка max.ru/...",
    )
    parser.add_argument(
        "--wait-bot-added",
        action="store_true",
        help="ждать событие bot_added после добавления бота в канал",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        dest="wait_timeout",
        help="таймаут ожидания bot_added в секундах (по умолчанию 120)",
    )
    args = parser.parse_args()
    asyncio.run(
        _run(
            args.platform_id,
            wait_bot_added=args.wait_bot_added,
            wait_timeout=args.wait_timeout,
        )
    )


if __name__ == "__main__":
    main()
