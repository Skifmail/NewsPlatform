"""WebSocket для realtime обновлений."""

import asyncio
import json
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.infrastructure.events import CHANNEL_UPDATES

router = APIRouter()


class ConnectionManager:
    """Менеджер WebSocket-подключений."""

    def __init__(self) -> None:
        self.active: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Принимает подключение."""
        await websocket.accept()
        self.active.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Отключает клиента."""
        if websocket in self.active:
            self.active.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Рассылает сообщение всем клиентам."""
        dead: list[WebSocket] = []
        for ws in self.active:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
_redis_task: asyncio.Task[None] | None = None


async def _redis_listener() -> None:
    """Слушает Redis pub/sub и рассылает в WebSocket."""
    settings = get_settings()
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(CHANNEL_UPDATES)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = message["data"]
            if isinstance(data, str):
                payload = json.loads(data)
                await manager.broadcast(payload)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("Redis listener error", error=str(exc))
    finally:
        await pubsub.unsubscribe(CHANNEL_UPDATES)
        await client.aclose()


def start_redis_listener() -> None:
    """Запускает фоновый listener (один на процесс)."""
    global _redis_task
    if _redis_task is None or _redis_task.done():
        _redis_task = asyncio.create_task(_redis_listener())


@router.websocket("/updates")
async def websocket_updates(websocket: WebSocket, token: str | None = None) -> None:
    """WebSocket /ws/updates — события activity (задачи, посты, публикации).

    Args:
        websocket: соединение.
        token: JWT из query (?token=...).
    """
    if not token or not decode_access_token(token):
        await websocket.close(code=1008, reason="Unauthorized")
        return
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
