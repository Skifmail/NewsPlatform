"""Сбор статистики Telegram-каналов.

Подписчиков получаем через Bot API (``getChatMemberCount``) — бот уже админ
канала и токен всегда настроен. Просмотры/реакции по постам собираем через
Telethon, если заданы ``TELEGRAM_API_ID``/``TELEGRAM_API_HASH``.
"""

from datetime import UTC, datetime

import aiohttp
from loguru import logger
from telethon import TelegramClient
from telethon.tl.functions.stats import GetBroadcastStatsRequest
from telethon.tl.types import Message

from app.core.config import get_settings
from app.infrastructure.models.channel import Channel
from app.infrastructure.parsers.telegram_parser import SESSION_PATH
from app.infrastructure.stats.telethon_lock import TelethonSessionBusyError, telethon_session_lock
from app.infrastructure.stats.base import (
    BaseStatsCollector,
    BroadcastStatsDTO,
    ChannelStatsDTO,
    PostMetricDTO,
)


def _abs_pair(value: object) -> tuple[float | None, float | None]:
    """Достаёт (current, previous) из StatsAbsValueAndPrev.

    Args:
        value: объект StatsAbsValueAndPrev или None.

    Returns:
        tuple[float | None, float | None]: текущее и предыдущее значения.
    """
    if value is None:
        return None, None
    cur = getattr(value, "current", None)
    prev = getattr(value, "previous", None)
    return (
        float(cur) if cur is not None else None,
        float(prev) if prev is not None else None,
    )


def _percent(value: object) -> float | None:
    """Считает процент из StatsPercentValue (part/total × 100).

    Args:
        value: объект StatsPercentValue или None.

    Returns:
        float | None: процент или None.
    """
    if value is None:
        return None
    part = getattr(value, "part", None)
    total = getattr(value, "total", None)
    if not total:
        return None
    return round(float(part) / float(total) * 100, 2)


def _period_dt(period: object, attr: str) -> datetime | None:
    """Извлекает границу периода (Unix-сек) из StatsDateRangeDays.

    Args:
        period: объект period или None.
        attr: min_date | max_date.

    Returns:
        datetime | None: момент UTC.
    """
    raw = getattr(period, attr, None)
    if not raw:
        return None
    try:
        return datetime.fromtimestamp(int(raw), tz=UTC)
    except (TypeError, ValueError, OverflowError):
        return None


def parse_broadcast_stats(stats: object) -> BroadcastStatsDTO:
    """Преобразует объект BroadcastStats Telethon в DTO (защищённо, getattr).

    Args:
        stats: результат GetBroadcastStatsRequest.

    Returns:
        BroadcastStatsDTO: скалярные показатели статистики канала.
    """
    followers, followers_prev = _abs_pair(getattr(stats, "followers", None))
    vpp, vpp_prev = _abs_pair(getattr(stats, "views_per_post", None))
    spp, spp_prev = _abs_pair(getattr(stats, "shares_per_post", None))
    rpp, rpp_prev = _abs_pair(getattr(stats, "reactions_per_post", None))
    period = getattr(stats, "period", None)
    return BroadcastStatsDTO(
        followers=followers,
        followers_prev=followers_prev,
        views_per_post=vpp,
        views_per_post_prev=vpp_prev,
        shares_per_post=spp,
        shares_per_post_prev=spp_prev,
        reactions_per_post=rpp,
        reactions_per_post_prev=rpp_prev,
        enabled_notifications_pct=_percent(
            getattr(stats, "enabled_notifications", None)
        ),
        period_min=_period_dt(period, "min_date"),
        period_max=_period_dt(period, "max_date"),
    )

_MAX_MESSAGES = 50
_TELEGRAM_BOT_API = "https://api.telegram.org"


def _normalize_telegram_channel(platform_id: str) -> str:
    """Приводит platform_id к виду @channel.

    Args:
        platform_id: username или ссылка t.me.

    Returns:
        str: @username.
    """
    channel = platform_id.strip().replace("https://t.me/", "").lstrip("@")
    return f"@{channel}"


def _is_numeric_chat_id(platform_id: str) -> bool:
    """Проверяет, что platform_id — числовой chat_id (например, -100123...).

    Args:
        platform_id: значение поля канала.

    Returns:
        bool: True если это числовой ID.
    """
    stripped = platform_id.strip()
    return stripped.lstrip("-").isdigit()


def _count_reactions(message: Message) -> int:
    """Суммирует реакции сообщения.

    Args:
        message: объект Telethon Message.

    Returns:
        int: количество реакций.
    """
    reactions = getattr(message, "reactions", None)
    if not reactions:
        return 0
    results = getattr(reactions, "results", None) or []
    return sum(getattr(item, "count", 0) for item in results)


def _message_published_at(message: Message):
    """Возвращает дату публикации сообщения в UTC.

    Args:
        message: объект Telethon Message.

    Returns:
        datetime | None: момент публикации.
    """
    msg_date = message.date
    if msg_date is None:
        return None
    if msg_date.tzinfo is None:
        return msg_date.replace(tzinfo=UTC)
    return msg_date


class TelegramStatsCollector(BaseStatsCollector):
    """Статистика Telegram: Bot API для подписчиков, Telethon для постов."""

    async def collect(
        self,
        channel: Channel,
        *,
        known_post_ids: list[str] | None = None,
    ) -> ChannelStatsDTO:
        """Собирает подписчиков (Bot API) и метрики постов (Telethon).

        Args:
            channel: канал Telegram.
            known_post_ids: ID сообщений для приоритетного сбора.

        Returns:
            ChannelStatsDTO: метрики.
        """
        settings = get_settings()

        subscribers = await self._fetch_subscribers_bot_api(
            settings.telegram_bot_token, channel.platform_id
        )

        telethon_ready = bool(
            settings.telegram_api_id and settings.telegram_api_hash
        )
        if not telethon_ready:
            if subscribers is None:
                logger.warning(
                    "Telegram analytics: no Bot API member count and Telethon "
                    "not configured",
                    channel_id=channel.id,
                )
            return ChannelStatsDTO(subscribers=subscribers)

        telethon_stats = await self._collect_via_telethon(
            settings, channel, known_post_ids or []
        )
        return ChannelStatsDTO(
            subscribers=subscribers or telethon_stats.subscribers,
            posts_count=telethon_stats.posts_count,
            total_views=telethon_stats.total_views,
            post_metrics=telethon_stats.post_metrics,
            broadcast_stats=telethon_stats.broadcast_stats,
        )

    async def _fetch_subscribers_bot_api(
        self, bot_token: str, platform_id: str
    ) -> int | None:
        """Получает число подписчиков через Bot API getChatMemberCount.

        Args:
            bot_token: токен бота.
            platform_id: chat_id или @username.

        Returns:
            int | None: число подписчиков или None при ошибке.
        """
        if not bot_token:
            return None

        if _is_numeric_chat_id(platform_id):
            chat_id: str = platform_id.strip()
        else:
            chat_id = _normalize_telegram_channel(platform_id)

        url = f"{_TELEGRAM_BOT_API}/bot{bot_token}/getChatMemberCount"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params={"chat_id": chat_id}) as resp:
                    data = await resp.json()
            if not data.get("ok"):
                logger.warning(
                    "Telegram getChatMemberCount failed",
                    chat_id=chat_id,
                    description=data.get("description"),
                )
                return None
            return int(data["result"])
        except Exception as exc:
            logger.warning(
                "Telegram Bot API member count error",
                chat_id=chat_id,
                error=str(exc),
            )
            return None

    async def _collect_via_telethon(
        self,
        settings: object,
        channel: Channel,
        known_post_ids: list[str],
    ) -> ChannelStatsDTO:
        """Собирает подписчиков и метрики постов через Telethon."""
        try:
            with telethon_session_lock():
                return await self._run_telethon_collect(
                    settings, channel, known_post_ids
                )
        except TelethonSessionBusyError as exc:
            logger.warning(
                "Telegram Telethon stats skipped: session busy",
                channel_id=channel.id,
                error=str(exc),
            )
            return ChannelStatsDTO()

    async def _run_telethon_collect(
        self,
        settings: object,
        channel: Channel,
        known_post_ids: list[str],
    ) -> ChannelStatsDTO:
        """Внутренний сбор через Telethon (под lock)."""
        username = _normalize_telegram_channel(channel.platform_id)
        target: str | int = (
            int(channel.platform_id.strip())
            if _is_numeric_chat_id(channel.platform_id)
            else username
        )
        known_ids = {pid.strip() for pid in known_post_ids if pid.strip()}

        client = TelegramClient(
            SESSION_PATH,
            settings.telegram_api_id,  # type: ignore[attr-defined]
            settings.telegram_api_hash,  # type: ignore[attr-defined]
        )
        await client.start(phone=settings.telegram_phone or None)  # type: ignore[attr-defined]
        try:
            entity = await client.get_entity(target)
            subscribers = getattr(entity, "participants_count", None)
            slug = getattr(entity, "username", None) or username.lstrip("@")

            post_metrics: list[PostMetricDTO] = []
            seen: set[str] = set()

            def _append(message: Message) -> None:
                if not message.id or str(message.id) in seen:
                    return
                seen.add(str(message.id))
                replies = getattr(message, "replies", None)
                post_metrics.append(
                    PostMetricDTO(
                        platform_post_id=str(message.id),
                        post_url=f"https://t.me/{slug}/{message.id}",
                        views=getattr(message, "views", None),
                        forwards=getattr(message, "forwards", None),
                        reactions=_count_reactions(message) or None,
                        comments=getattr(replies, "replies", None) if replies else None,
                        published_at=_message_published_at(message),
                    )
                )

            for post_id in known_ids:
                try:
                    message = await client.get_messages(entity, ids=int(post_id))
                except (ValueError, TypeError):
                    continue
                if isinstance(message, Message):
                    _append(message)

            async for message in client.iter_messages(entity, limit=_MAX_MESSAGES):
                if isinstance(message, Message):
                    _append(message)

            broadcast_stats = await self._fetch_broadcast_stats(client, entity, channel)

            total_views = sum(m.views or 0 for m in post_metrics if m.views)
            return ChannelStatsDTO(
                subscribers=subscribers,
                posts_count=len(post_metrics) if post_metrics else None,
                total_views=total_views or None,
                post_metrics=post_metrics,
                broadcast_stats=broadcast_stats,
            )
        except Exception as exc:
            logger.warning(
                "Telegram Telethon stats failed",
                channel_id=channel.id,
                error=str(exc),
            )
            return ChannelStatsDTO()
        finally:
            await client.disconnect()

    async def _fetch_broadcast_stats(
        self, client: TelegramClient, entity: object, channel: Channel
    ) -> BroadcastStatsDTO | None:
        """Собирает нативную статистику канала (stats.getBroadcastStats).

        Защищённо: статистика доступна лишь для достаточно крупных каналов и
        при user-аккаунте-администраторе. Для мелких/новых каналов Telegram
        отвечает ошибкой — тогда тихо возвращаем None (сбор не ломается).
        Как только канал дорастёт до порога, статистика начнёт наполняться
        автоматически. Данные могут жить на другом DC — обрабатываем
        StatsMigrateError через отдельный sender.

        Args:
            client: подключённый Telethon-клиент (user-сессия).
            entity: сущность канала.
            channel: канал (для логов).

        Returns:
            BroadcastStatsDTO | None: показатели или None, если недоступно.
        """
        from telethon.errors import StatsMigrateError

        request = GetBroadcastStatsRequest(channel=entity, dark=False)
        try:
            try:
                result = await client(request)
            except StatsMigrateError as migrate:
                sender = await client._borrow_exported_sender(migrate.dc)
                try:
                    result = await sender.send(request)
                finally:
                    await client._return_exported_sender(sender)
            return parse_broadcast_stats(result)
        except Exception as exc:
            logger.debug(
                "Telegram broadcast stats unavailable (channel likely too small)",
                channel_id=channel.id,
                error=str(exc),
            )
            return None
