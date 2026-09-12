"""Независимые от статей задания подготовки и доставки дополнений."""

from datetime import UTC, datetime
from typing import Final

from loguru import logger
from sqlalchemy import select

from app.domain.supplements import SupplementError
from app.infrastructure.database import async_session_factory
from app.infrastructure.models.supplement import SupplementConfig, SupplementDraft
from app.services.supplement_service import SupplementService
from app.tasks.async_runner import run_async
from app.tasks.celery_app import celery_app

_BATCH_SIZE: Final = 50


@celery_app.task(name="app.tasks.supplement_tasks.tick")  # type: ignore[untyped-decorator]
def supplement_tick() -> None:
    """Резервирует слоты и доставляет сохранённые решения даже после сбоя брокера."""

    async def work() -> None:
        async with async_session_factory() as session:
            service = SupplementService(session)
            await service.recover_stale()
            channel_ids = list(
                await session.scalars(
                    select(SupplementConfig.channel_id).where(
                        SupplementConfig.enabled.is_(True)
                    )
                )
            )
            for channel_id in channel_ids:
                try:
                    await service.reserve(channel_id, now=datetime.now(UTC))
                except SupplementError as exc:
                    await session.rollback()
                    logger.warning(
                        "Слот дополнения пропущен",
                        channel_id=channel_id,
                        reason=str(exc),
                    )
            pending = list(
                (
                    await session.execute(
                        select(SupplementDraft.id, SupplementDraft.status)
                        .where(
                            SupplementDraft.status.in_(
                                ["queued", "review_pending", "approved"]
                            )
                        )
                        .order_by(SupplementDraft.id)
                        .limit(_BATCH_SIZE)
                    )
                ).all()
            )
            await session.commit()
            for draft_id, state in pending:
                if state == "queued":
                    generate_supplement.delay(draft_id)
                elif state == "approved":
                    await service.publish(draft_id)
                else:
                    await service.deliver(draft_id)

    run_async(work())


@celery_app.task(name="app.tasks.supplement_tasks.generate")  # type: ignore[untyped-decorator]
def generate_supplement(draft_id: int) -> None:
    """Генерирует один материал в выделенной AI-очереди.

    Args:
        draft_id: Сохранённое задание.
    """

    async def work() -> None:
        async with async_session_factory() as session:
            service = SupplementService(session)
            await service.generate(draft_id)
            await service.deliver(draft_id)

    run_async(work())


@celery_app.task(name="app.tasks.supplement_tasks.publish")  # type: ignore[untyped-decorator]
def publish_supplement(draft_id: int) -> None:
    """Быстро доставляет уже сохранённое одобрение.

    Args:
        draft_id: Одобренный материал.
    """

    async def work() -> None:
        async with async_session_factory() as session:
            await SupplementService(session).publish(draft_id)

    run_async(work())
