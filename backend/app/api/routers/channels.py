"""Роутер каналов."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AuthDep, DbSession
from app.api.schemas.channel import (
    ChannelCreate,
    ChannelResponse,
    ChannelUpdate,
    GenerateArticleRequest,
    TopicQueueAppendRequest,
    TopicQueueItemAction,
)
from app.api.schemas.common import MessageResponse
from app.domain.enums import ContentMode
from app.infrastructure.models.channel import Channel
from app.domain.topic_queue import (
    append_topics,
    mark_skipped,
    parse_topic_queue,
    parse_topics_from_text,
    queue_summary,
    serialize_topic_queue,
)
from app.repositories.channel_repository import ChannelRepository
from app.tasks.article_tasks import generate_article_task

router = APIRouter(prefix="/channels", tags=["channels"])


@router.get("", response_model=list[ChannelResponse])
async def list_channels(session: DbSession, _: AuthDep) -> list[Channel]:
    """Список каналов."""
    return await ChannelRepository(session).list_all()


@router.post("", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_channel(
    data: ChannelCreate, session: DbSession, _: AuthDep
) -> Channel:
    """Добавляет канал."""
    repo = ChannelRepository(session)
    channel = Channel(**data.model_dump())
    created = await repo.create(channel)
    await session.commit()
    return created


@router.patch("/{channel_id}", response_model=ChannelResponse)
async def update_channel(
    channel_id: int, data: ChannelUpdate, session: DbSession, _: AuthDep
) -> Channel:
    """Редактирует канал (включая style_prompt)."""
    repo = ChannelRepository(session)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    payload = data.model_dump(exclude_unset=True)
    for key, value in payload.items():
        setattr(channel, key, value)
    updated = await repo.update(channel)
    await session.commit()
    return updated


@router.delete("/{channel_id}", response_model=MessageResponse)
async def delete_channel(
    channel_id: int, session: DbSession, _: AuthDep
) -> MessageResponse:
    """Удаляет канал."""
    repo = ChannelRepository(session)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    await repo.delete(channel)
    await session.commit()
    return MessageResponse(message="Deleted")


@router.post("/{channel_id}/generate-article", response_model=MessageResponse)
async def generate_article(
    channel_id: int,
    session: DbSession,
    _: AuthDep,
    body: GenerateArticleRequest = GenerateArticleRequest(),
) -> MessageResponse:
    """Ставит в очередь генерацию статьи для article-канала."""
    repo = ChannelRepository(session)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    if channel.content_mode != ContentMode.ARTICLE.value:
        raise HTTPException(
            status_code=400,
            detail="Канал не в режиме «Статьи»",
        )
    cleaned = (body.topic or "").strip()
    manual_topic = cleaned or None
    result = generate_article_task.delay(channel_id, topic=manual_topic)
    from app.services.job_tracker import JobTracker

    await JobTracker(session).enqueue_article(
        result.id,
        channel.id,
        channel.name,
    )
    await session.commit()
    return MessageResponse(
        message=f"Генерация статьи запущена (task {result.id})",
    )


@router.get("/{channel_id}/topic-queue")
async def get_topic_queue(
    channel_id: int, session: DbSession, _: AuthDep
) -> dict:
    """Возвращает редакционную очередь тем и сводку статусов."""
    channel = await ChannelRepository(session).get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    items = parse_topic_queue(channel.topic_queue)
    return {
        "items": [item.to_dict() for item in items],
        "summary": queue_summary(items),
    }


@router.post("/{channel_id}/topic-queue", response_model=ChannelResponse)
async def append_topic_queue(
    channel_id: int,
    body: TopicQueueAppendRequest,
    session: DbSession,
    _: AuthDep,
):
    """Добавляет темы (по одной на строку) в конец очереди."""
    repo = ChannelRepository(session)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    titles = parse_topics_from_text(body.topics_text)
    if not titles:
        raise HTTPException(status_code=400, detail="Список тем пуст")
    items = append_topics(parse_topic_queue(channel.topic_queue), titles)
    channel.topic_queue = serialize_topic_queue(items)
    updated = await repo.update(channel)
    await session.commit()
    return updated


@router.post("/{channel_id}/topic-queue/action", response_model=ChannelResponse)
async def topic_queue_action(
    channel_id: int,
    body: TopicQueueItemAction,
    session: DbSession,
    _: AuthDep,
):
    """Пропускает тему или возвращает в pending."""
    repo = ChannelRepository(session)
    channel = await repo.get_by_id(channel_id)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    items = parse_topic_queue(channel.topic_queue)
    if body.action == "skip":
        items = mark_skipped(items, body.item_id)
    elif body.action == "restore_pending":
        restored = []
        for item in items:
            if item.id == body.item_id and item.status == "skipped":
                from app.domain.topic_queue import TopicQueueItem
                restored.append(
                    TopicQueueItem(
                        id=item.id,
                        title=item.title,
                        status="pending",
                        entities=list(item.entities),
                        notes=item.notes,
                    )
                )
            else:
                restored.append(item)
        items = restored
    channel.topic_queue = serialize_topic_queue(items)
    updated = await repo.update(channel)
    await session.commit()
    return updated

