"""Сброс слота планировщика статей после окончательного провала генерации."""

from loguru import logger

from app.domain.article import article_scheduler_key
from app.infrastructure.database import async_session_factory
from app.repositories.setting_repository import SettingRepository


async def release_article_scheduler_slot(channel_id: int) -> None:
    """Сбрасывает отметку слота, чтобы catch-up мог повторить генерацию в тот же день."""
    async with async_session_factory() as session:
        repo = SettingRepository(session)
        await repo.set(article_scheduler_key(channel_id), "")
        await session.commit()
    logger.warning(
        "Article scheduler slot released after generation failure",
        channel_id=channel_id,
    )
