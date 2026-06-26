"""Тест публикации длинного поста через Telethon userbot.

По умолчанию — канал АВТОСФЕРА (без подписчиков).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infrastructure.models.channel import Channel
from app.infrastructure.publishers.telegram_user_publisher import (
    TelegramUserPublisher,
    TelethonPublishError,
)
from app.utils.text_format import strip_html_tags

_DEFAULT_CHAT_ID = "-1004244141982"
_MINI_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
    "wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/"
    "8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k="
)


def _build_test_text(target_visible: int) -> str:
    """HTML-текст ~target_visible видимых символов."""
    header = (
        "<b>[USERBOT-TEST]</b>\n\n"
        "<i>Проверка: одно сообщение, фото + длинная подпись через Telethon (до 4096).</i>\n\n"
        "<b>Раздел</b>\n\n"
    )
    paragraph = (
        "Электромобили меняют рынок: зарядная инфраструктура растёт, "
        "а автопроизводители пересматривают линейки. "
    )
    body_len = max(0, target_visible - len(strip_html_tags(header)))
    repeats = (body_len // len(paragraph)) + 1
    body = (paragraph * repeats)[:body_len]
    return f"{header}{body}"


def _channel_link(platform_id: str, message_id: str) -> str:
    chat = platform_id.strip().removeprefix("-100")
    return f"https://t.me/c/{chat}/{message_id}"


async def run_probe(chat_id: str, visible_chars: int, delete_after: bool) -> None:
    """Публикует тест и выводит отчёт."""
    channel = Channel(
        id=2,
        name="АВТОСФЕРА | Новости",
        platform="telegram",
        platform_id=chat_id,
        topic="auto",
    )
    text = _build_test_text(visible_chars)
    publisher = TelegramUserPublisher()

    print(f"Публикация в {chat_id}…")
    print(f"  символов в строке: {len(text)}")
    print(f"  видимых символов:  {len(strip_html_tags(text))}")

    try:
        message_id = await publisher.publish(channel, text, _MINI_JPEG)
    except TelethonPublishError as exc:
        print(f"ОШИБКА: {exc}")
        raise SystemExit(1) from exc

    link = _channel_link(chat_id, message_id)
    print(f"OK: message_id={message_id}")
    print(f"Ссылка: {link}")

    if delete_after:
        from telethon import TelegramClient

        from app.core.config import get_settings
        from app.infrastructure.parsers.telegram_parser import SESSION_PATH

        settings = get_settings()
        client = TelegramClient(
            SESSION_PATH,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
        await client.connect()
        await client.delete_messages(int(chat_id), [int(message_id)])
        await client.disconnect()
        print("Тестовое сообщение удалено.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Тест userbot-публикации в Telegram")
    parser.add_argument(
        "chat_id",
        nargs="?",
        default=_DEFAULT_CHAT_ID,
        help=f"chat_id канала (по умолчанию {_DEFAULT_CHAT_ID})",
    )
    parser.add_argument(
        "--chars",
        type=int,
        default=3000,
        help="целевое число видимых символов (по умолчанию 3000)",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="не удалять сообщение после публикации",
    )
    args = parser.parse_args()
    asyncio.run(run_probe(args.chat_id, args.chars, delete_after=not args.keep))


if __name__ == "__main__":
    main()
