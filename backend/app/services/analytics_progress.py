"""Отслеживание прогресса сбора статистики каналов через Redis.

Прогресс пишется синхронным клиентом из Celery-задачи и читается асинхронным
клиентом из FastAPI-эндпоинта. Состояние живёт ограниченное время (TTL),
чтобы фронтенд успел дочитать финальный статус после завершения задачи.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import redis
import redis.asyncio as aioredis
from loguru import logger

from app.core.config import get_settings

_PROGRESS_TTL_SEC = 600
_KEY_PREFIX = "analytics:refresh:progress:"


def _key(job_id: str) -> str:
    """Возвращает Redis-ключ прогресса для задачи."""
    return f"{_KEY_PREFIX}{job_id}"


def _now_iso() -> str:
    """Текущее время UTC в ISO-формате."""
    return datetime.now(UTC).isoformat()


@dataclass
class ChannelProgress:
    """Прогресс по одному каналу."""

    id: int
    name: str
    platform: str
    status: str = "pending"  # pending | running | success | failed
    subscribers: int | None = None
    posts: int | None = None
    total_views: int | None = None
    error: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


@dataclass
class RefreshProgress:
    """Полное состояние одной задачи сбора статистики."""

    job_id: str
    status: str = "running"  # running | done | error
    total: int = 0
    completed: int = 0
    started_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    channels: list[ChannelProgress] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Сериализует состояние в словарь."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RefreshProgress:
        """Восстанавливает состояние из словаря."""
        channels = [ChannelProgress(**ch) for ch in data.get("channels", [])]
        payload = {**data, "channels": channels}
        return cls(**payload)


class RefreshProgressWriter:
    """Синхронный писатель прогресса для Celery-задач."""

    def __init__(self, job_id: str) -> None:
        self._job_id = job_id
        self._client = redis.from_url(get_settings().redis_url)
        self._state = RefreshProgress(job_id=job_id)

    @property
    def job_id(self) -> str:
        """ID задачи (Celery task id)."""
        return self._job_id

    def init(self, channels: list[tuple[int, str, str]]) -> None:
        """Инициализирует список каналов в статусе pending.

        Args:
            channels: список кортежей (id, name, platform).
        """
        self._state.channels = [
            ChannelProgress(id=cid, name=name, platform=platform)
            for cid, name, platform in channels
        ]
        self._state.total = len(self._state.channels)
        self._state.completed = 0
        self._state.status = "running"
        self._flush()

    def _find(self, channel_id: int) -> ChannelProgress | None:
        """Находит запись канала по id."""
        for channel in self._state.channels:
            if channel.id == channel_id:
                return channel
        return None

    def mark_running(self, channel_id: int) -> None:
        """Помечает канал как опрашиваемый сейчас."""
        channel = self._find(channel_id)
        if channel is None:
            return
        channel.status = "running"
        channel.started_at = _now_iso()
        self._flush()

    def mark_done(
        self,
        channel_id: int,
        *,
        success: bool,
        subscribers: int | None = None,
        posts: int | None = None,
        total_views: int | None = None,
        error: str | None = None,
    ) -> None:
        """Помечает канал как завершённый (успех/ошибка) и пишет метрики."""
        channel = self._find(channel_id)
        if channel is None:
            return
        channel.status = "success" if success else "failed"
        channel.subscribers = subscribers
        channel.posts = posts
        channel.total_views = total_views
        channel.error = error
        channel.finished_at = _now_iso()
        self._state.completed += 1
        self._flush()

    def finish(self, *, status: str = "done") -> None:
        """Завершает задачу целиком."""
        self._state.status = status
        self._state.finished_at = _now_iso()
        self._flush()

    def _flush(self) -> None:
        """Сохраняет текущее состояние в Redis с TTL."""
        try:
            self._client.set(
                _key(self._job_id),
                json.dumps(self._state.to_dict()),
                ex=_PROGRESS_TTL_SEC,
            )
        except Exception as exc:  # noqa: BLE001 - прогресс не должен ронять задачу
            logger.warning(
                "Failed to write analytics refresh progress",
                job_id=self._job_id,
                error=str(exc),
            )


async def read_progress(job_id: str) -> dict[str, Any] | None:
    """Читает прогресс задачи (для FastAPI-эндпоинта).

    Args:
        job_id: Celery task id.

    Returns:
        dict | None: состояние задачи или None, если её нет / истёк TTL.
    """
    client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        raw = await client.get(_key(job_id))
    finally:
        await client.aclose()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
