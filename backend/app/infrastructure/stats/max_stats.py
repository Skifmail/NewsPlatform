"""Сбор статистики MAX-каналов через Bot API.

Подписчиков и число сообщений берём из ``GET /chats/{chatId}``
(``participants_count`` / ``messages_count``). Просмотры по постам — из
``GET /messages?message_ids=...`` (поле ``stat.views``), которое MAX отдаёт
только для постов в каналах и только боту с правом ``view_stats``.
"""

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import aiohttp
from loguru import logger

from app.core.config import get_settings
from app.infrastructure.models.channel import Channel
from app.infrastructure.stats.base import (
    BaseStatsCollector,
    ChannelStatsDTO,
    PostMetricDTO,
)
from app.utils.max_api import get_max_api_base, max_client_session

_NUMERIC_CHAT_ID_RE = re.compile(r"^-?\d+$")

_MESSAGE_IDS_BATCH = 100


def parse_max_chat_info(payload: dict[str, Any]) -> tuple[int | None, int | None]:
    """Извлекает participants_count и messages_count из ответа GET /chats.

    Args:
        payload: JSON MAX API.

    Returns:
        tuple[int | None, int | None]: подписчики, число сообщений.
    """
    participants = payload.get("participants_count")
    messages = payload.get("messages_count")
    return (
        int(participants) if participants is not None else None,
        int(messages) if messages is not None else None,
    )


def _extract_message_id(message: dict[str, Any]) -> str | None:
    """Извлекает идентификатор сообщения (mid) из объекта Message MAX.

    Args:
        message: объект Message из ответа GET /messages.

    Returns:
        str | None: идентификатор поста или None.
    """
    for key in ("message_id", "mid", "id"):
        value = message.get(key)
        if value is not None:
            return str(value)
    body = message.get("body")
    if isinstance(body, dict):
        for key in ("mid", "message_id", "id"):
            value = body.get(key)
            if value is not None:
                return str(value)
    return None


def _parse_published_at(message: dict[str, Any]) -> datetime | None:
    """Преобразует Unix-time (мс) в datetime UTC.

    Args:
        message: объект Message из ответа GET /messages.

    Returns:
        datetime | None: момент публикации или None.
    """
    timestamp = message.get("timestamp")
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000, tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def parse_max_message_metrics(payload: dict[str, Any]) -> list[PostMetricDTO]:
    """Извлекает метрики постов канала из ответа GET /messages.

    MAX возвращает ``stat.views`` только для постов в каналах. Реакции,
    репосты, комментарии и охват API не отдаёт, поэтому заполняем только
    просмотры, публичную ссылку и дату публикации.

    Args:
        payload: JSON ответа GET /messages.

    Returns:
        list[PostMetricDTO]: метрики постов с известными просмотрами.
    """
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return []

    metrics: list[PostMetricDTO] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        message_id = _extract_message_id(message)
        if message_id is None:
            continue
        stat = message.get("stat")
        views = stat.get("views") if isinstance(stat, dict) else None
        url = message.get("url")
        metrics.append(
            PostMetricDTO(
                platform_post_id=message_id,
                post_url=url if isinstance(url, str) and url else None,
                views=int(views) if views is not None else None,
                published_at=_parse_published_at(message),
            )
        )
    return metrics


def normalize_max_chat_link(platform_id: str) -> str:
    """Извлекает slug канала из ссылки или @username.

    Args:
        platform_id: chat_id или ссылка max.ru.

    Returns:
        str: slug для GET /chats/{link}.
    """
    stripped = platform_id.strip()
    if "max.ru/" in stripped.lower():
        path = urlparse(stripped).path.strip("/")
        return path.split("/")[-1]
    if stripped.startswith("@"):
        return stripped[1:]
    return stripped


class MaxStatsCollector(BaseStatsCollector):
    """Статистика MAX: подписчики, число сообщений и просмотры постов."""

    async def collect(
        self,
        channel: Channel,
        *,
        known_post_ids: list[str] | None = None,
    ) -> ChannelStatsDTO:
        """Собирает participants_count, messages_count и просмотры постов.

        Args:
            channel: канал MAX.
            known_post_ids: ID опубликованных постов для сбора ``stat.views``.

        Returns:
            ChannelStatsDTO: метрики канала и постов.
        """
        settings = get_settings()
        if not settings.max_bot_token:
            logger.warning("MAX_BOT_TOKEN not configured for analytics")
            return ChannelStatsDTO()

        async with max_client_session() as session:
            payload = await self._fetch_chat(session, settings.max_bot_token, channel.platform_id)
            if not payload:
                return ChannelStatsDTO()
            post_metrics = await self._fetch_post_metrics(
                session, settings.max_bot_token, known_post_ids or []
            )

        subscribers, messages_count = parse_max_chat_info(payload)
        total_views = sum(m.views or 0 for m in post_metrics if m.views)
        return ChannelStatsDTO(
            subscribers=subscribers,
            posts_count=messages_count,
            total_views=total_views or None,
            post_metrics=post_metrics,
        )

    async def _fetch_post_metrics(
        self,
        session: aiohttp.ClientSession,
        token: str,
        known_post_ids: list[str],
    ) -> list[PostMetricDTO]:
        """Собирает просмотры известных постов через GET /messages.

        Запрашивает посты пачками по ``message_ids`` (до 100 за раз) и читает
        ``stat.views``. Недоступность статистики (нет права ``view_stats``)
        логируется и не прерывает сбор остальных метрик канала.

        Args:
            session: HTTP-сессия с доверием к CA Минцифры.
            token: токен бота.
            known_post_ids: ID опубликованных постов.

        Returns:
            list[PostMetricDTO]: метрики постов с просмотрами.
        """
        unique_ids = list(dict.fromkeys(pid.strip() for pid in known_post_ids if pid.strip()))
        if not unique_ids:
            return []

        metrics: list[PostMetricDTO] = []
        for start in range(0, len(unique_ids), _MESSAGE_IDS_BATCH):
            batch = unique_ids[start : start + _MESSAGE_IDS_BATCH]
            payload = await self._fetch_messages(session, token, batch)
            if payload:
                metrics.extend(parse_max_message_metrics(payload))
        return metrics

    async def _fetch_messages(
        self,
        session: aiohttp.ClientSession,
        token: str,
        message_ids: list[str],
    ) -> dict[str, Any] | None:
        """GET /messages?message_ids=... для одной пачки идентификаторов."""
        url = f"{get_max_api_base()}/messages"
        headers = {"Authorization": token}
        params = {"message_ids": ",".join(message_ids)}
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.warning(
                        "MAX message stats failed",
                        status=resp.status,
                        body=body[:200],
                    )
                    return None
                data = await resp.json()
                return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.warning("MAX message stats collection failed", error=str(exc))
            return None

    async def _fetch_chat(
        self,
        session: aiohttp.ClientSession,
        token: str,
        platform_id: str,
    ) -> dict[str, Any] | None:
        """GET /chats/{chatId|link}."""
        raw = platform_id.strip()
        chat_ref = raw if _NUMERIC_CHAT_ID_RE.fullmatch(raw) else normalize_max_chat_link(raw)
        url = f"{get_max_api_base()}/chats/{chat_ref}"
        headers = {"Authorization": token}
        try:
            async with session.get(url, headers=headers) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.warning(
                        "MAX chat info failed",
                        status=resp.status,
                        body=body[:200],
                    )
                    return None
                data = await resp.json()
                if not isinstance(data, dict):
                    return None
                return data
        except Exception as exc:
            logger.warning("MAX stats collection failed", error=str(exc))
            return None
