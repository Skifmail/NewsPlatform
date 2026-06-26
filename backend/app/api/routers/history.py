"""Роутер истории публикаций."""

from fastapi import APIRouter, Query

from app.api.deps import AuthDep, DbSession
from app.api.schemas.post import PublishHistoryResponse
from app.repositories.publish_log_repository import PublishLogRepository

router = APIRouter(prefix="/history", tags=["history"])


@router.get("", response_model=list[PublishHistoryResponse])
async def get_history(
    session: DbSession,
    _: AuthDep,
    channel_id: int | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[PublishHistoryResponse]:
    """История попыток публикации (успешные и с ошибкой)."""
    logs = await PublishLogRepository(session).list_history(
        channel_id=channel_id, limit=limit, offset=offset
    )
    items: list[PublishHistoryResponse] = []
    for log in logs:
        post = log.processed_post
        items.append(
            PublishHistoryResponse(
                id=log.id,
                processed_post_id=log.processed_post_id,
                channel=post.channel if post else None,
                status=log.status,
                error_message=log.error_message,
                attempted_at=log.published_at,
                rewritten_text=post.rewritten_text if post else None,
            )
        )
    return items
