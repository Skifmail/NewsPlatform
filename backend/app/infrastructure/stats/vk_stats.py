"""Сбор статистики VK-сообществ через API."""

from datetime import UTC, datetime
from typing import Any

import aiohttp
from loguru import logger

from app.core.config import get_settings
from app.infrastructure.models.channel import Channel
from app.infrastructure.stats.base import (
    BaseStatsCollector,
    ChannelStatsDTO,
    PostMetricDTO,
)

_VK_API = "https://api.vk.com/method"


def _vk_post_published_at(item: dict[str, Any]) -> datetime | None:
    """Преобразует unix-время VK в datetime UTC.

    Args:
        item: объект поста из wall API.

    Returns:
        datetime | None: момент публикации.
    """
    ts = item.get("date")
    if ts is None:
        return None
    return datetime.fromtimestamp(int(ts), tz=UTC)


def _with_reach(metric: PostMetricDTO, reach: int | None) -> PostMetricDTO:
    """Возвращает копию метрик с обновлённым охватом."""
    return PostMetricDTO(
        platform_post_id=metric.platform_post_id,
        post_url=metric.post_url,
        views=metric.views,
        forwards=metric.forwards,
        reactions=metric.reactions,
        comments=metric.comments,
        reach=reach,
        published_at=metric.published_at,
    )


def parse_vk_group_members(payload: dict[str, Any]) -> int | None:
    """Извлекает members_count из ответа groups.getById.

    Args:
        payload: JSON VK API.

    Returns:
        int | None: число подписчиков.
    """
    if "error" in payload:
        return None
    groups = payload.get("response") or []
    if not groups:
        return None
    return groups[0].get("members_count")


def parse_vk_wall_post(payload: dict[str, Any]) -> PostMetricDTO | None:
    """Парсит метрики одного поста из wall.getById.

    Args:
        payload: JSON VK API.

    Returns:
        PostMetricDTO | None: метрики поста.
    """
    if "error" in payload:
        return None
    items = payload.get("response") or []
    if not items:
        return None
    item = items[0]
    post_id = str(item.get("id", ""))
    owner_id = item.get("owner_id")
    if not post_id or owner_id is None:
        return None
    return PostMetricDTO(
        platform_post_id=post_id,
        post_url=f"https://vk.com/wall{owner_id}_{post_id}",
        views=item.get("views", {}).get("count") if isinstance(item.get("views"), dict) else item.get("views"),
        comments=item.get("comments", {}).get("count")
        if isinstance(item.get("comments"), dict)
        else item.get("comments"),
        forwards=item.get("reposts", {}).get("count")
        if isinstance(item.get("reposts"), dict)
        else item.get("reposts"),
        reactions=item.get("likes", {}).get("count")
        if isinstance(item.get("likes"), dict)
        else item.get("likes"),
        published_at=_vk_post_published_at(item),
    )


def parse_vk_post_reach(payload: dict[str, Any]) -> int | None:
    """Извлекает суммарный охват из stats.getPostReach.

    Args:
        payload: JSON VK API.

    Returns:
        int | None: reach_total.
    """
    if "error" in payload:
        return None
    items = payload.get("response") or []
    if not items:
        return None
    stat = items[0]
    return stat.get("reach_total") or stat.get("reach_subscribers")


class VkStatsCollector(BaseStatsCollector):
    """Статистика VK через wall и stats API."""

    async def collect(
        self,
        channel: Channel,
        *,
        known_post_ids: list[str] | None = None,
    ) -> ChannelStatsDTO:
        """Собирает подписчиков и метрики постов VK.

        Args:
            channel: канал VK (platform_id = owner_id, например -123456).
            known_post_ids: ID постов на стене.

        Returns:
            ChannelStatsDTO: метрики.
        """
        settings = get_settings()
        if not settings.vk_access_token:
            logger.warning("VK_ACCESS_TOKEN not configured for analytics")
            return ChannelStatsDTO()

        owner_id = channel.platform_id.strip()
        group_id = abs(int(owner_id)) if owner_id.startswith("-") else None

        async with aiohttp.ClientSession() as session:
            subscribers = await self._fetch_subscribers(
                session, settings.vk_access_token, settings.vk_api_version, group_id, owner_id
            )
            post_metrics = await self._fetch_post_metrics(
                session,
                settings.vk_access_token,
                settings.vk_api_version,
                owner_id,
                known_post_ids or [],
            )

        total_views = sum(m.views or 0 for m in post_metrics if m.views)
        return ChannelStatsDTO(
            subscribers=subscribers,
            posts_count=len(post_metrics) if post_metrics else None,
            total_views=total_views or None,
            post_metrics=post_metrics,
        )

    async def _fetch_subscribers(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_version: str,
        group_id: int | None,
        owner_id: str,
    ) -> int | None:
        """Запрашивает members_count сообщества."""
        if group_id is None:
            return None
        params = {
            "access_token": token,
            "v": api_version,
            "group_ids": str(group_id),
            "fields": "members_count",
        }
        async with session.get(f"{_VK_API}/groups.getById", params=params) as resp:
            data = await resp.json()
        if "error" in data:
            logger.warning("VK groups.getById failed", error=data["error"])
            return None
        return parse_vk_group_members(data)

    async def _fetch_post_metrics(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_version: str,
        owner_id: str,
        known_post_ids: list[str],
    ) -> list[PostMetricDTO]:
        """Собирает метрики известных постов и последних записей стены."""
        metrics: list[PostMetricDTO] = []
        seen: set[str] = set()

        for post_id in known_post_ids:
            pid = post_id.strip()
            if not pid or pid in seen:
                continue
            metric = await self._fetch_single_post(
                session, token, api_version, owner_id, pid
            )
            if metric:
                reach = await self._fetch_reach(
                    session, token, api_version, owner_id, pid
                )
                if reach is not None:
                    metric = _with_reach(metric, reach)
                metrics.append(metric)
                seen.add(pid)

        if not known_post_ids:
            wall_posts = await self._fetch_recent_wall(
                session, token, api_version, owner_id
            )
            for metric in wall_posts:
                if metric.platform_post_id not in seen:
                    metrics.append(metric)
                    seen.add(metric.platform_post_id)

        return metrics

    async def _fetch_single_post(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_version: str,
        owner_id: str,
        post_id: str,
    ) -> PostMetricDTO | None:
        """Метрики одного поста wall.getById."""
        params = {
            "access_token": token,
            "v": api_version,
            "posts": f"{owner_id}_{post_id}",
        }
        async with session.get(f"{_VK_API}/wall.getById", params=params) as resp:
            data = await resp.json()
        if "error" in data:
            logger.debug("VK wall.getById failed", post_id=post_id, error=data["error"])
            return None
        return parse_vk_wall_post(data)

    async def _fetch_reach(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_version: str,
        owner_id: str,
        post_id: str,
    ) -> int | None:
        """Охват поста stats.getPostReach."""
        params = {
            "access_token": token,
            "v": api_version,
            "owner_id": owner_id,
            "post_id": post_id,
        }
        async with session.get(f"{_VK_API}/stats.getPostReach", params=params) as resp:
            data = await resp.json()
        if "error" in data:
            logger.debug(
                "VK stats.getPostReach failed", post_id=post_id, error=data["error"]
            )
            return None
        return parse_vk_post_reach(data)

    async def _fetch_recent_wall(
        self,
        session: aiohttp.ClientSession,
        token: str,
        api_version: str,
        owner_id: str,
        count: int = 30,
    ) -> list[PostMetricDTO]:
        """Последние посты со стены."""
        params = {
            "access_token": token,
            "v": api_version,
            "owner_id": owner_id,
            "count": count,
        }
        async with session.get(f"{_VK_API}/wall.get", params=params) as resp:
            data = await resp.json()
        if "error" in data:
            logger.warning("VK wall.get failed", error=data["error"])
            return []

        items = (data.get("response") or {}).get("items") or []
        result: list[PostMetricDTO] = []
        for item in items:
            post_id = str(item.get("id", ""))
            if not post_id:
                continue
            metric = PostMetricDTO(
                platform_post_id=post_id,
                post_url=f"https://vk.com/wall{owner_id}_{post_id}",
                views=item.get("views", {}).get("count")
                if isinstance(item.get("views"), dict)
                else item.get("views"),
                comments=item.get("comments", {}).get("count")
                if isinstance(item.get("comments"), dict)
                else item.get("comments"),
                forwards=item.get("reposts", {}).get("count")
                if isinstance(item.get("reposts"), dict)
                else item.get("reposts"),
                reactions=item.get("likes", {}).get("count")
                if isinstance(item.get("likes"), dict)
                else item.get("likes"),
                published_at=_vk_post_published_at(item),
            )
            reach = await self._fetch_reach(
                session, token, api_version, owner_id, post_id
            )
            if reach is not None:
                metric = _with_reach(metric, reach)
            result.append(metric)
        return result
