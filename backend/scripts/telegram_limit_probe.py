"""Эмпирическая проверка лимитов Telegram Bot API для канала.

Бинарным поиском находит максимальную длину:
- текстового сообщения (без фото);
- подписи к фото (с картинкой).

Сообщения помечаются префиксом [LIMIT-PROBE] — их можно удалить вручную.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import sys
from pathlib import Path

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import BufferedInputFile
from loguru import logger

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings  # noqa: E402
from app.utils.text_format import (  # noqa: E402
    TELEGRAM_BOT_CAPTION_MAX,
    TELEGRAM_MESSAGE_MAX,
    strip_html_tags,
)

# Канал без аудитории — безопасен для проб (АВТОСФЕРА | Новости).
_DEFAULT_PROBE_CHAT_ID = "-1004244141982"

_PROBE_PREFIX = "[LIMIT-PROBE] "
_PROBE_DELAY_SEC = 0.4
# Минимальная валидная JPEG 1×1.
_MINI_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////"
    "2wBDAf//////////////////////////////////////////////////////////////////////////////////////"
    "wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAb/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/"
    "8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdABmX/9k="
)


def _is_too_long_error(exc: TelegramBadRequest) -> bool:
    message = str(exc).lower()
    return "too long" in message or "too_long" in message


def _build_plain_text(target_len: int) -> str:
    """Текст фиксированной длины (без HTML)."""
    body_len = max(0, target_len - len(_PROBE_PREFIX))
    return f"{_PROBE_PREFIX}{'а' * body_len}"


def _build_html_text(target_len: int) -> str:
    """Текст с HTML-разметкой как в реальных постах."""
    link = '<a href="https://example.com/article">Читать в источнике →</a>'
    footer = f"\n\n{link}"
    prefix = _PROBE_PREFIX
    # Оставляем место под теги <b></b> вокруг основного текста.
    open_tag, close_tag = "<b>", "</b>"
    overhead = len(prefix) + len(open_tag) + len(close_tag) + len(footer)
    body_len = max(0, target_len - overhead)
    return f"{prefix}{open_tag}{'б' * body_len}{close_tag}{footer}"


async def _probe_max(
    bot: Bot,
    chat_id: str,
    *,
    with_photo: bool,
    build_text,
    low: int,
    high: int,
) -> tuple[int, str | None]:
    """Бинарный поиск максимальной принимаемой длины."""
    best = 0
    last_error: str | None = None
    photo = BufferedInputFile(_MINI_JPEG, filename="probe.jpg")

    while low <= high:
        mid = (low + high) // 2
        text = build_text(mid)
        actual_len = len(text)
        await asyncio.sleep(_PROBE_DELAY_SEC)
        try:
            if with_photo:
                msg = await bot.send_photo(
                    chat_id=chat_id,
                    photo=photo,
                    caption=text,
                    parse_mode=ParseMode.HTML,
                )
            else:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode=ParseMode.HTML,
                )
            best = actual_len
            last_error = None
            low = mid + 1
            # Удаляем успешное тестовое сообщение, чтобы не засорять канал.
            try:
                await bot.delete_message(chat_id=chat_id, message_id=msg.message_id)
            except Exception as del_exc:
                logger.warning("Не удалось удалить probe-сообщение: {}", del_exc)
        except TelegramRetryAfter as exc:
            logger.warning("Flood control, ждём {} с", exc.retry_after)
            await asyncio.sleep(exc.retry_after + 1)
            continue
        except TelegramBadRequest as exc:
            if _is_too_long_error(exc):
                last_error = str(exc)
                high = mid - 1
            else:
                raise
    return best, last_error


async def run_probe(chat_id: str, html: bool) -> None:
    """Запускает все пробы и печатает отчёт."""
    settings = get_settings()
    if not settings.telegram_bot_token:
        msg = "TELEGRAM_BOT_TOKEN не задан"
        raise RuntimeError(msg)

    build = _build_html_text if html else _build_plain_text
    mode = "HTML (как в постах)" if html else "plain"

    bot = Bot(token=settings.telegram_bot_token)
    try:
        logger.info("Проба текстового сообщения без фото ({})", mode)
        msg_max, msg_err = await _probe_max(
            bot,
            chat_id,
            with_photo=False,
            build_text=build,
            low=1,
            high=4500,
        )

        logger.info("Проба подписи к фото ({})", mode)
        cap_max, cap_err = await _probe_max(
            bot,
            chat_id,
            with_photo=True,
            build_text=build,
            low=1,
            high=1200,
        )

        print("\n=== Telegram limit probe ===")
        print(f"Канал: {chat_id}")
        print(f"Режим текста: {mode}")
        print()
        if html:
            vis_msg = len(strip_html_tags(build(msg_max)))
            vis_cap = len(strip_html_tags(build(cap_max)))
            print(
                f"Сообщение без фото:  до {msg_max} символов в строке ({vis_msg} видимых)"
            )
        else:
            print(f"Сообщение без фото:  до {msg_max} символов")
        print(f"  лимит Bot API: {TELEGRAM_MESSAGE_MAX} (видимый текст после разбора HTML)")
        if msg_err:
            print(f"  ошибка на границе: {msg_err}")
        if html:
            print(
                f"Подпись к фото:      до {cap_max} символов в строке ({vis_cap} видимых)"
            )
        else:
            print(f"Подпись к фото:      до {cap_max} символов")
        print(f"  лимит Bot API: {TELEGRAM_BOT_CAPTION_MAX} (видимый текст после разбора HTML)")
        if cap_err:
            print(f"  ошибка на границе: {cap_err}")
        print()
        if not html and msg_max == TELEGRAM_MESSAGE_MAX and cap_max == TELEGRAM_BOT_CAPTION_MAX:
            print("✓ Константы в text_format.py совпадают с Bot API")
        elif html:
            if vis_msg <= TELEGRAM_MESSAGE_MAX and vis_cap <= TELEGRAM_BOT_CAPTION_MAX:
                print("✓ Видимый текст укладывается в лимиты Bot API (HTML-теги в лимит не входят)")
            print("ℹ В режиме --html длина строки с тегами больше — это нормально.")
    finally:
        await bot.session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка лимитов Telegram Bot API")
    parser.add_argument(
        "chat_id",
        nargs="?",
        default=_DEFAULT_PROBE_CHAT_ID,
        help=f"ID канала (@username или -100...), по умолчанию {_DEFAULT_PROBE_CHAT_ID} (АВТОСФЕРА)",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Тест с HTML-разметкой (b, a) как в реальных постах",
    )
    args = parser.parse_args()
    asyncio.run(run_probe(args.chat_id, html=args.html))


if __name__ == "__main__":
    main()
