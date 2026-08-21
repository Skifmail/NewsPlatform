"""Webhook MAX Bot API: callback-кнопки постов Параграфа.

Callers: FastAPI app (main.py). API: POST /api/webhooks/max.
Schemas: message_callback Update, post_metrics.button_clicks.
User instruction: implement expert recommendations for Параграф MAX —
interactive callback buttons with personal answer notification.
"""

from __future__ import annotations

from typing import Any

import aiohttp
from fastapi import APIRouter, Header, HTTPException, Request, status
from loguru import logger

from app.api.deps import DbSession
from app.core.config import get_settings
from app.domain.article_meta import parse_article_meta
from app.infrastructure.publishers.max_keyboard import parse_callback_payload
from app.repositories.post_metrics_repository import PostMetricsRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.utils.max_api import get_max_api_base, max_client_session

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/max")
async def max_webhook(
    request: Request,
    session: DbSession,
    x_max_bot_api_secret: str | None = Header(None, alias="X-Max-Bot-Api-Secret"),
) -> dict[str, str]:
    """Принимает Update от MAX (message_callback и др.).

    Args:
        request: сырой HTTP-запрос.
        session: БД-сессия.
        x_max_bot_api_secret: секрет подписки (если настроен).

    Returns:
        dict: статус обработки.
    """
    settings = get_settings()
    expected = (getattr(settings, "max_webhook_secret", None) or "").strip()
    if expected and x_max_bot_api_secret != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad secret")

    payload: dict[str, Any] = await request.json()
    update_type = str(payload.get("update_type") or payload.get("type") or "")
    if update_type != "message_callback":
        return {"status": "ignored", "update_type": update_type}

    callback = payload.get("callback") or {}
    callback_id = str(callback.get("callback_id") or "")
    cb_payload = str(callback.get("payload") or "")
    post_id, option_idx = parse_callback_payload(cb_payload)
    notification = "Спасибо! Ответ записан."

    if post_id is not None:
        post = await ProcessedPostRepository(session).get_by_id(post_id)
        if post is not None:
            meta = parse_article_meta(post.article_meta)
            options = meta.button_options
            if option_idx is not None and 0 <= option_idx < len(options):
                notification = f"Ваш выбор: {options[option_idx]}"
            await _increment_button_clicks(session, post.id)
            await session.commit()

    if callback_id and settings.max_bot_token:
        await _answer_callback(settings.max_bot_token, callback_id, notification)

    return {"status": "ok"}


async def _increment_button_clicks(session: DbSession, processed_post_id: int) -> None:
    """Увеличивает счётчик нажатий кнопок у метрик поста."""
    repo = PostMetricsRepository(session)
    metric = await repo.get_by_processed_post_id(processed_post_id)
    if metric is None:
        logger.debug(
            "MAX callback: no post_metric yet",
            processed_post_id=processed_post_id,
        )
        return
    metric.button_clicks = int(metric.button_clicks or 0) + 1
    await session.flush()


async def _answer_callback(token: str, callback_id: str, notification: str) -> None:
    """Отправляет персональный ответ на callback (не светит ответ всем)."""
    body = {"notification": notification[:200]}
    try:
        async with max_client_session() as http:
            async with http.post(
                f"{get_max_api_base()}/answers",
                params={"callback_id": callback_id},
                headers={"Authorization": token, "Content-Type": "application/json"},
                json=body,
            ) as resp:
                if resp.status >= 400:
                    raw = await resp.text()
                    logger.warning(
                        "MAX answer callback failed",
                        status=resp.status,
                        body=raw[:300],
                    )
    except aiohttp.ClientError as exc:
        logger.warning("MAX answer callback error", error=str(exc))
