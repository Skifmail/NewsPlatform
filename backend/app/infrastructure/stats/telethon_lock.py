"""Блокировка файла сессии Telethon между параллельными задачами."""

from contextlib import contextmanager
from typing import Iterator

import redis
from loguru import logger

from app.core.config import get_settings

_LOCK_KEY = "lock:telethon:session"
_LOCK_TIMEOUT_SEC = 180
_BLOCKING_TIMEOUT_SEC = 90


class TelethonSessionBusyError(RuntimeError):
    """Сессия Telethon уже используется другой задачей."""


@contextmanager
def telethon_session_lock() -> Iterator[None]:
    """Эксклюзивный доступ к session-файлу Telethon.

    Yields:
        None

    Raises:
        TelethonSessionBusyError: не удалось захватить lock за отведённое время.
    """
    settings = get_settings()
    client = redis.from_url(settings.redis_url)
    lock = client.lock(
        _LOCK_KEY,
        timeout=_LOCK_TIMEOUT_SEC,
        blocking_timeout=_BLOCKING_TIMEOUT_SEC,
    )
    acquired = lock.acquire(blocking=True)
    if not acquired:
        msg = "Telethon session is busy (another task is using it)"
        logger.warning(msg)
        raise TelethonSessionBusyError(msg)
    try:
        yield
    finally:
        try:
            lock.release()
        except redis.exceptions.LockNotOwnedError:
            pass
