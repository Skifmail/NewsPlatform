"""Роутер источников."""

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AuthDep, DbSession
from app.api.schemas.common import MessageResponse
from app.api.schemas.job import FetchQueuedResponse
from app.api.schemas.source import SourceCreate, SourceResponse, SourceUpdate
from app.infrastructure.models.source import Source
from app.repositories.source_repository import SourceRepository
from app.services.job_tracker import JobTracker
from app.api.deps_platform import require_manual_fetch
from app.tasks.fetch_tasks import fetch_source_task

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[SourceResponse])
async def list_sources(session: DbSession, _: AuthDep) -> list[Source]:
    """Список источников."""
    return await SourceRepository(session).list_all()


@router.post("", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    data: SourceCreate, session: DbSession, _: AuthDep
) -> Source:
    """Добавляет источник."""
    repo = SourceRepository(session)
    source = Source(**data.model_dump())
    created = await repo.create(source)
    await session.commit()
    return created


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int, data: SourceUpdate, session: DbSession, _: AuthDep
) -> Source:
    """Редактирует источник."""
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    updated = await repo.update(source)
    await session.commit()
    return updated


@router.delete("/{source_id}", response_model=MessageResponse)
async def delete_source(
    source_id: int, session: DbSession, _: AuthDep
) -> MessageResponse:
    """Удаляет источник."""
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await repo.delete(source)
    await session.commit()
    return MessageResponse(message="Deleted")


@router.post("/{source_id}/fetch_now", response_model=FetchQueuedResponse)
async def fetch_now(
    source_id: int, session: DbSession, _: AuthDep
) -> FetchQueuedResponse:
    """Ставит парсинг источника в очередь Celery (Redis).

    Статус смотрите в разделе «Задачи» панели.
    """
    repo = SourceRepository(session)
    source = await repo.get_by_id(source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await require_manual_fetch(session)
    result = fetch_source_task.delay(source_id, manual=True)
    job = await JobTracker(session).enqueue_fetch(
        result.id, source_id, source.name
    )
    await session.commit()
    return FetchQueuedResponse(
        message="Парсинг поставлен в очередь Celery",
        celery_task_id=result.id,
        job_id=job.id,
    )
