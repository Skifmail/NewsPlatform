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
    MemberDTO,
    PostMetricDTO,
)
from app.utils.max_api import get_max_api_base, max_client_session

_NUMERIC_CHAT_ID_RE = re.compile(r"^-?\d+$")

# message_id у MAX длинные (~37 символов: "mid." + 32 hex). Запрос GET /messages
# передаёт их в query-строке; при ~90+ id URL превышает лимит длины MAX и он
# отвечает HTTP 400 "Invalid HTTP request". 40 (~1500 символов) — с запасом.
_MESSAGE_IDS_BATCH = 40
_MEMBERS_PAGE = 100
_MEMBERS_MAX_PAGES = 200


def _ms_to_dt(value: object) -> datetime | None:
    """Преобразует Unix-time в миллисекундах в datetime UTC.

    Args:
        value: метка времени в мс (0 и None трактуются как «нет данных»).

    Returns:
        datetime | None: момент времени или None.
    """
    if not value:
        return None
    try:
        return datetime.fromtimestamp(int(value) / 1000, tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def parse_max_member(raw: dict[str, Any]) -> MemberDTO | None:
    """Извлекает участника канала из объекта ChatMember MAX.

    Args:
        raw: элемент массива ``members`` ответа GET /chats/{id}/members.

    Returns:
        MemberDTO | None: участник или None, если нет user_id.
    """
    user_id = raw.get("user_id")
    if user_id is None:
        return None
    permissions = raw.get("permissions")
    return MemberDTO(
        user_id=int(user_id),
        first_name=raw.get("first_name") or None,
        last_name=raw.get("last_name") or None,
        name=raw.get("name") or None,
        username=raw.get("username") or None,
        avatar_url=raw.get("avatar_url") or raw.get("full_avatar_url") or None,
        is_bot=bool(raw.get("is_bot", False)),
        is_admin=bool(raw.get("is_admin", False)),
        is_owner=bool(raw.get("is_owner", False)),
        permissions=[str(p) for p in permissions] if isinstance(permissions, list) else None,
        join_at=_ms_to_dt(raw.get("join_time")),
        last_access_at=_ms_to_dt(raw.get("last_access_time")),
        last_activity_at=_ms_to_dt(raw.get("last_activity_time")),
    )


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
            members = await self._fetch_all_members(
                session, settings.max_bot_token, channel.platform_id
            )

        subscribers, messages_count = parse_max_chat_info(payload)
        total_views = sum(m.views or 0 for m in post_metrics if m.views)
        return ChannelStatsDTO(
            subscribers=subscribers,
            posts_count=messages_count,
            total_views=total_views or None,
            post_metrics=post_metrics,
            members=members,
        )

    async def _fetch_all_members(
        self,
        session: aiohttp.ClientSession,
        token: str,
        platform_id: str,
    ) -> list[MemberDTO]:
        """Собирает всех участников канала с пагинацией по ``marker``.

        Требует у бота права администратора канала. Недоступность
        (нет прав / приватный чат) логируется и не прерывает сбор
        остальных метрик.

        Args:
            session: HTTP-сессия с доверием к CA Минцифры.
            token: токен бота.
            platform_id: chat_id или ссылка канала.

        Returns:
            list[MemberDTO]: все участники (включая ботов и админов).
        """
        raw = platform_id.strip()
        chat_ref = raw if _NUMERIC_CHAT_ID_RE.fullmatch(raw) else normalize_max_chat_link(raw)
        url = f"{get_max_api_base()}/chats/{chat_ref}/members"
        headers = {"Authorization": token}
        members: list[MemberDTO] = []
        marker: str | int | None = None
        for _ in range(_MEMBERS_MAX_PAGES):
            params: dict[str, str | int] = {"count": _MEMBERS_PAGE}
            if marker is not None:
                params["marker"] = marker
            try:
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status >= 400:
                        body = await resp.text()
                        logger.warning(
                            "MAX members fetch failed",
                            status=resp.status,
                            body=body[:200],
                        )
                        break
                    data = await resp.json()
            except Exception as exc:
                logger.warning("MAX members collection failed", error=str(exc))
                break
            if not isinstance(data, dict):
                break
            batch = data.get("members")
            if not isinstance(batch, list) or not batch:
                break
            for item in batch:
                if isinstance(item, dict) and (parsed := parse_max_member(item)):
                    members.append(parsed)
            marker = data.get("marker")
            if not marker:
                break
        return members

    async def _fetch_post_metrics(
        self,
        session: aiohttp.ClientSession,
        token: str,
        known_post_ids: list[str],
    ) -> list[PostMetricDTO]:
        """Собирает просмотры известных постов через GET /messages.

        Запрашивает посты пачками по ``_MESSAGE_IDS_BATCH`` и читает
        ``stat.views``. Каждая пачка собирается адаптивно
        (``_collect_messages_adaptive``): при ошибке дробится пополам, поэтому
        рост канала или битый id не замораживают сбор. Недоступность
        статистики (нет права ``view_stats``) не прерывает остальные метрики.

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
            metrics.extend(await self._collect_messages_adaptive(session, token, batch))
        return metrics

    async def _collect_messages_adaptive(
        self,
        session: aiohttp.ClientSession,
        token: str,
        message_ids: list[str],
    ) -> list[PostMetricDTO]:
        """Собирает метрики пачки, дробя её пополам при ошибке запроса.

        Самовосстановление: если MAX отвечает ошибкой (слишком длинный URL,
        битый/удалённый id и т.п.), пачка делится надвое и повторяется вплоть
        до одного id. Один проблемный пост изолируется и пропускается, а
        остальные всё равно собираются — сбор не «замерзает» с ростом канала.

        Args:
            session: HTTP-сессия.
            token: токен бота.
            message_ids: идентификаторы постов одной пачки.

        Returns:
            list[PostMetricDTO]: метрики успешно полученных постов.
        """
        if not message_ids:
            return []
        payload = await self._fetch_messages(session, token, message_ids)
        if payload is not None:
            return parse_max_message_metrics(payload)

        if len(message_ids) == 1:
            logger.warning(
                "MAX message stats: пропуск поста после ошибки",
                message_id=message_ids[0],
            )
            return []

        mid = len(message_ids) // 2
        left = await self._collect_messages_adaptive(session, token, message_ids[:mid])
        right = await self._collect_messages_adaptive(session, token, message_ids[mid:])
        return left + right

    async def _fetch_messages(
        self,
        session: aiohttp.ClientSession,
        token: str,
        message_ids: list[str],
    ) -> dict[str, Any] | None:
        """GET /messages?message_ids=... для одной пачки идентификаторов.

        Возвращает None при ошибке — вызывающий (`_collect_messages_adaptive`)
        сам дробит пачку и повторяет, поэтому здесь ошибка не критична и
        логируется на уровне debug.
        """
        url = f"{get_max_api_base()}/messages"
        headers = {"Authorization": token}
        params = {"message_ids": ",".join(message_ids)}
        try:
            async with session.get(url, headers=headers, params=params) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.debug(
                        "MAX message stats batch failed, will split",
                        status=resp.status,
                        batch_size=len(message_ids),
                        body=body[:200],
                    )
                    return None
                data = await resp.json()
                return data if isinstance(data, dict) else None
        except Exception as exc:
            logger.debug(
                "MAX message stats batch error, will split",
                batch_size=len(message_ids),
                error=str(exc),
            )
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
