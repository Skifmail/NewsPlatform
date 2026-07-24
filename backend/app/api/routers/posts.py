"""Роутер очереди постов."""

from fastapi import APIRouter, HTTPException

from app.api.deps import AuthDep, DbSession
from app.api.deps_platform import require_manual_publish
from app.api.schemas.common import BulkActionResponse, MessageResponse
from app.api.schemas.post import (
    ApproveRequest,
    ApprovedSummaryResponse,
    ProcessedPostResponse,
    QueueBulkRequest,
    RejectRequest,
    UpdatePostRequest,
)
from app.domain.enums import PostStatus
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.services.image_refresh_service import ImageRefreshService
from app.services.job_tracker import JobTracker
from app.services.moderation_service import ModerationService
from app.services.post_response_service import PostResponseService
from app.tasks.publish_tasks import publish_post_task

router = APIRouter(prefix="/posts", tags=["posts"])


@router.get("/queue", response_model=list[ProcessedPostResponse])
async def get_queue(session: DbSession, _: AuthDep) -> list[ProcessedPost]:
    """Очередь pending постов."""
    return await ProcessedPostRepository(session).list_queue()


@router.post("/queue/bulk", response_model=BulkActionResponse)
async def bulk_queue_action(
    body: QueueBulkRequest,
    session: DbSession,
    _: AuthDep,
) -> BulkActionResponse:
    """Массовое отклонение или удаление постов из очереди модерации."""
    return await ModerationService(session).bulk_queue_action(body)


@router.get("/approved", response_model=list[ProcessedPostResponse])
async def get_approved(session: DbSession, _: AuthDep) -> list[ProcessedPostResponse]:
    """Очередь публикации: одобренные и посты с ошибкой (для повтора)."""
    posts = await ProcessedPostRepository(session).list_approved()
    return await PostResponseService(session).to_responses(posts)


@router.get("/approved/summary", response_model=ApprovedSummaryResponse)
async def get_approved_summary(session: DbSession, _: AuthDep) -> ApprovedSummaryResponse:
    """Счётчик одобренных постов для бокового меню."""
    total = await ProcessedPostRepository(session).count_approved()
    return ApprovedSummaryResponse(total=total)


@router.get("/{post_id}", response_model=ProcessedPostResponse)
async def get_post(
    post_id: int, session: DbSession, _: AuthDep
) -> ProcessedPost:
    """Детальный просмотр поста."""
    post = await ProcessedPostRepository(session).get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


@router.patch("/{post_id}", response_model=ProcessedPostResponse)
async def update_post(
    post_id: int,
    data: UpdatePostRequest,
    session: DbSession,
    _: AuthDep,
) -> ProcessedPost:
    """Редактирует текст или картинку поста."""
    try:
        return await ModerationService(session).update_content(
            post_id,
            rewritten_text=data.rewritten_text,
            generated_image_url=data.generated_image_url,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{post_id}", response_model=MessageResponse)
async def delete_post(
    post_id: int, session: DbSession, _: AuthDep
) -> MessageResponse:
    """Удаляет пост (кроме уже опубликованных)."""
    try:
        await ModerationService(session).delete_post(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MessageResponse(message="Deleted")


@router.post("/{post_id}/refresh-image", response_model=ProcessedPostResponse)
async def refresh_post_image(
    post_id: int, session: DbSession, _: AuthDep
) -> ProcessedPost:
    """Подтягивает изображение из оригинала или страницы источника."""
    try:
        return await ImageRefreshService(session).refresh_from_source(post_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{post_id}/approve", response_model=ProcessedPostResponse)
async def approve_post(
    post_id: int,
    data: ApproveRequest,
    session: DbSession,
    _: AuthDep,
) -> ProcessedPost:
    """Одобряет пост."""
    if data.publish_immediately:
        await require_manual_publish(session)
    try:
        return await ModerationService(session).approve(
            post_id,
            rewritten_text=data.rewritten_text,
            generated_image_url=data.generated_image_url,
            publish_immediately=data.publish_immediately,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.patch("/{post_id}/reject", response_model=ProcessedPostResponse)
async def reject_post(
    post_id: int, data: RejectRequest, session: DbSession, _: AuthDep
) -> ProcessedPost:
    """Отклоняет пост."""
    try:
        return await ModerationService(session).reject(post_id, data.reason)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{post_id}/publish_now", response_model=MessageResponse)
async def publish_now(
    post_id: int, session: DbSession, _: AuthDep
) -> MessageResponse:
    """Публикует немедленно через Celery."""
    await require_manual_publish(session)
    repo = ProcessedPostRepository(session)
    post = await repo.get_by_id(post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status not in (
        PostStatus.APPROVED.value,
        PostStatus.FAILED.value,
        PostStatus.PENDING.value,
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Post cannot be published (status={post.status})",
        )
    if post.status in (PostStatus.PENDING.value, PostStatus.FAILED.value):
        post.status = PostStatus.APPROVED.value
        await repo.update(post)
    channel_name = post.channel.name if post.channel else "Канал"
    task = publish_post_task.delay(post_id)
    await JobTracker(session).enqueue_publish(task.id, post_id, channel_name)
    await session.commit()
    return MessageResponse(message="Publish task queued")


