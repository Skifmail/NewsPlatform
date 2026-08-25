"""Кэш токенов видео MAX: повторная публикация без повторной заливки файла.

Callers: MaxPublisher — get/set после POST /uploads?type=video.
Redis key: SHA-256(generated_video_url), TTL 48h.
User: «если нажму повторить всё начнется заново» — токен переживает retry.
"""

from __future__ import annotations

import hashlib

import redis
from loguru import logger

from app.core.config import get_settings

_KEY_PREFIX = "max:video_token:"
_TTL_SECONDS = 48 * 60 * 60


def _client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


def _key(video_source: str) -> str:
    digest = hashlib.sha256(video_source.encode("utf-8")).hexdigest()
    return f"{_KEY_PREFIX}{digest}"


def get_cached_max_video_token(video_source: str | None) -> str | None:
    """Достаёт сохранённый token вложения MAX для URL видео."""
    if not video_source:
        return None
    try:
        value = _client().get(_key(video_source))
    except redis.RedisError as exc:
        logger.warning("MAX video token cache get failed", error=str(exc))
        return None
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def set_cached_max_video_token(video_source: str | None, token: str) -> None:
    """Сохраняет token вложения MAX для последующих повторов публикации."""
    if not video_source or not token:
        return
    try:
        _client().setex(_key(video_source), _TTL_SECONDS, token)
    except redis.RedisError as exc:
        logger.warning("MAX video token cache set failed", error=str(exc))


def clear_cached_max_video_token(video_source: str | None) -> None:
    """Удаляет устаревший token (например после 404 от GET /videos)."""
    if not video_source:
        return
    try:
        _client().delete(_key(video_source))
    except redis.RedisError as exc:
        logger.warning("MAX video token cache delete failed", error=str(exc))
