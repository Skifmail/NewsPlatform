"""Запуск async-кода из синхронных Celery-задач."""

import asyncio
from collections.abc import Coroutine
from typing import TypeVar

from app.infrastructure.database import engine

T = TypeVar("T")


def run_async(coro: Coroutine[object, object, T]) -> T:
    """Выполняет корутину в отдельном event loop для prefork worker.

    После каждой задачи сбрасывает пул asyncpg, иначе соединения остаются
    привязанными к закрытому loop (RuntimeError: attached to a different loop).

    Args:
        coro: корутина.

    Returns:
        T: результат.
    """
    async def _run() -> T:
        try:
            return await coro
        finally:
            await engine.dispose()

    return asyncio.run(_run())
