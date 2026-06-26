"""Redis pub/sub для WebSocket broadcast."""

import json

import redis.asyncio as aioredis

from app.core.config import get_settings

CHANNEL_UPDATES = "platform:updates"


async def publish_event(event_type: str, payload: dict[str, object]) -> None:
    """Публикует событие в Redis.

    Args:
        event_type: тип события.
        payload: данные.
    """
    settings = get_settings()
    client = aioredis.from_url(settings.redis_url, decode_responses=True)
    try:
        message = json.dumps({"type": event_type, "payload": payload})
        await client.publish(CHANNEL_UPDATES, message)
    finally:
        await client.aclose()
