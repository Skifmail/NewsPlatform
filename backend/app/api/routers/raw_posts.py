"""Роутер сырых постов (материалы до AI)."""

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import AuthDep, DbSession
from app.api.deps_platform import require_manual_ai
from app.api.schemas.common import BulkActionResponse
from app.api.schemas.raw_post import (
    ProcessRawPostQueuedItem,
    ProcessRawPostsBatchResponse,
    ProcessRawPostRequest,
    RawPostBulkDeleteRequest,
    RawPostResponse,
    RawPostsSummaryResponse,
    RawPostSourceStats,
)
from app.domain.enums import Topic
from app.infrastructure.models.raw_post import RawPost
from app.repositories.raw_post_repository import RawPostRepository
from app.services.raw_post_service import RawPostService, content_preview

router = APIRouter(prefix="/raw-posts", tags=["raw-posts"])


def _to_response(post: RawPost) -> RawPostResponse:
    """Собирает ответ API из ORM-модели.

    Args:
        post: RawPost с relationship source.

    Returns:
        RawPostResponse: DTO для панели.
    """
    source_name = post.source.name if post.source else "—"
    source_url = post.source.url if post.source else ""
    return RawPostResponse(
        id=post.id,
        source_id=post.source_id,
        source_name=source_name,
        source_url=source_url,
        external_id=post.external_id,
        title=post.title,
        content_preview=content_preview(post.content),
        url=post.url,
        topic=post.topic,
        is_processed=post.is_processed,
        fetched_at=post.fetched_at,
        published_at=post.published_at,
    )


@router.get("/summary", response_model=RawPostsSummaryResponse)
async def raw_posts_summary(
    session: DbSession,
    _: AuthDep,
) -> RawPostsSummaryResponse:
    """Сводка сырых постов по источникам.

    Returns:
        RawPostsSummaryResponse: счётчики для фильтров и бейджа меню.
    """
    repo = RawPostRepository(session)
    rows = await repo.stats_by_source()
    sources = [
        RawPostSourceStats(
            source_id=sid,
            source_name=name,
            topic=topic,
            total=total,
            unprocessed=unprocessed,
        )
        for sid, name, topic, total, unprocessed in rows
    ]
    total_all = sum(s.total for s in sources)
    unprocessed_all = sum(s.unprocessed for s in sources)
    return RawPostsSummaryResponse(
        total=total_all,
        unprocessed=unprocessed_all,
        sources=sources,
    )


@router.get("", response_model=list[RawPostResponse])
async def list_raw_posts(
    session: DbSession,
    _: AuthDep,
    source_id: int | None = None,
    topic: Topic | None = None,
    is_processed: bool | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[RawPostResponse]:
    """Список сырых постов с фильтром по источнику и статусу AI.

    Args:
        source_id: ID источника (опционально).
        topic: тема материала (it/auto/russia).
        is_processed: True/False — только обработанные или ожидающие AI.
        limit: размер страницы.
        offset: смещение.

    Returns:
        list[RawPostResponse]: материалы для вкладки «Материалы».
    """
    posts = await RawPostRepository(session).list_filtered(
        source_id=source_id,
        topic=topic,
        is_processed=is_processed,
        limit=limit,
        offset=offset,
    )
    return [_to_response(p) for p in posts]


@router.post("/bulk-delete", response_model=BulkActionResponse)
async def bulk_delete_raw_posts(
    body: RawPostBulkDeleteRequest,
    session: DbSession,
    _: AuthDep,
) -> BulkActionResponse:
    """Массовое удаление сырых постов (материалов)."""
    return await RawPostService(session).bulk_delete(body)


@router.post("/{raw_post_id}/process", response_model=ProcessRawPostQueuedItem)
async def process_raw_post(
    raw_post_id: int,
    session: DbSession,
    _: AuthDep,
) -> ProcessRawPostQueuedItem:
    """Вручную ставит сырой пост на AI-обработку.

    Args:
        raw_post_id: ID raw_post.

    Returns:
        ProcessRawPostQueuedItem: ID задачи Celery.

    Raises:
        HTTPException: пост не найден или уже обработан.
    """
    await require_manual_ai(session)
    service = RawPostService(session)
    queued = await service.enqueue_processing(raw_post_id)
    if not queued:
        repo = RawPostRepository(session)
        raw = await repo.get_by_id(raw_post_id)
        if not raw:
            raise HTTPException(status_code=404, detail="Raw post not found")
        if raw.is_processed and await repo.count_processed_children(raw_post_id) > 0:
            raise HTTPException(
                status_code=400,
                detail="Пост уже в очереди модерации или опубликован",
            )
        raise HTTPException(
            status_code=400,
            detail="Не удалось поставить задачу в очередь",
        )
    job_id, celery_id = queued
    await session.commit()
    return ProcessRawPostQueuedItem(
        raw_post_id=raw_post_id,
        job_id=job_id,
        celery_task_id=celery_id,
    )


@router.post("/process-batch", response_model=ProcessRawPostsBatchResponse)
async def process_raw_posts_batch(
    body: ProcessRawPostRequest,
    session: DbSession,
    _: AuthDep,
) -> ProcessRawPostsBatchResponse:
    """Пакетно ставит сырые посты на AI-обработку.

    Args:
        body: список ID raw_post (до 50).

    Returns:
        ProcessRawPostsBatchResponse: поставленные и пропущенные ID.
    """
    await require_manual_ai(session)
    service = RawPostService(session)
    queued: list[ProcessRawPostQueuedItem] = []
    skipped: list[int] = []
    for raw_post_id in body.raw_post_ids:
        result = await service.enqueue_processing(raw_post_id)
        if result is None:
            skipped.append(raw_post_id)
            continue
        job_id, celery_id = result
        queued.append(
            ProcessRawPostQueuedItem(
                raw_post_id=raw_post_id,
                job_id=job_id,
                celery_task_id=celery_id,
            )
        )
    await session.commit()
    return ProcessRawPostsBatchResponse(
        message=f"В очередь AI поставлено: {len(queued)}",
        queued=queued,
        skipped=skipped,
    )
