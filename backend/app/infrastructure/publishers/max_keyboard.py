"""Сборка inline_keyboard для публикаций MAX Bot API.

Callers: MaxPublisher. Schema: attachments[{type:inline_keyboard}].
User: expert rec — callback buttons for engagement on Параграф MAX posts.
"""

from __future__ import annotations

from typing import Any


def build_callback_keyboard(
    options: list[str],
    *,
    payload_prefix: str,
    max_buttons: int = 3,
) -> dict[str, Any] | None:
    """Собирает attachment inline_keyboard с callback-кнопками.

    Args:
        options: подписи кнопок (2–3 варианта).
        payload_prefix: префикс payload, например ``pq:42``.
        max_buttons: максимум кнопок в одном ряду.

    Returns:
        dict | None: attachment для POST /messages или None.
    """
    cleaned = [opt.strip() for opt in options if opt and opt.strip()][:max_buttons]
    if len(cleaned) < 2:
        return None
    buttons = [
        [
            {
                "type": "callback",
                "text": label[:64],
                "payload": f"{payload_prefix}:{idx}",
            }
            for idx, label in enumerate(cleaned)
        ]
    ]
    return {
        "type": "inline_keyboard",
        "payload": {"buttons": buttons},
    }


def parse_callback_payload(payload: str) -> tuple[int | None, int | None]:
    """Разбирает payload вида ``pq:{processed_post_id}:{option_index}``.

    Args:
        payload: строка из message_callback.

    Returns:
        tuple: (processed_post_id, option_index) или (None, None).
    """
    parts = (payload or "").strip().split(":")
    if len(parts) != 3 or parts[0] != "pq":
        return None, None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None, None
