"""Роутер каналов."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AuthDep, DbSession
from app.api.schemas.channel import ChannelCreate, ChannelResponse, ChannelUpdate, GenerateArticleRequest
from app.api.schemas.common import MessageResponse
from app.domain.enums import ContentMode
from app.infrastructure.models.channel import Channel
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
