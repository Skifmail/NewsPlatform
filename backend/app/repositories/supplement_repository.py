"""Доступ к состояниям дополнительных публикаций."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.supplements import HISTORY_LIMIT, SupplementError
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.models.supplement import SupplementConfig, SupplementDraft


class SupplementRepository:
    """Изолирует SQL и блокировки записей.

    Attributes:
        session: Сессия транзакции вызывающего сервиса.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Сохраняет сессию.

        Args:
            session: Текущая сессия БД.
        """
        self.session = session

    async def config(self, channel_id: int) -> SupplementConfig:
        """Возвращает или создаёт настройки под блокировкой канала.

        Args:
            channel_id: Канал MAX.

        Returns:
            Настройки рубрики.

        Raises:
            SupplementError: Канал отсутствует или не является MAX-каналом.
        """
        channel = await self.session.scalar(
            select(Channel).where(Channel.id == channel_id).with_for_update()
        )
        if channel is None or channel.platform != "max":
            raise SupplementError("Дополнительные материалы доступны для каналов MAX")
        config = await self.session.get(
            SupplementConfig, channel_id, populate_existing=True
        )
        if config is None:
            config = SupplementConfig(channel_id=channel_id)
            self.session.add(config)
            await self.session.flush()
        return config

    async def draft(self, draft_id: int) -> SupplementDraft:
        """Читает черновик с блокировкой для атомарного перехода состояния.

        Args:
            draft_id: Идентификатор.

        Returns:
            Актуальная запись.

        Raises:
            SupplementError: Черновик не найден.
        """
        draft = await self.session.scalar(
            select(SupplementDraft)
            .where(SupplementDraft.id == draft_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if draft is None:
            raise SupplementError("Материал не найден")
        return draft

    async def history(self, channel_id: int, exclude_id: int) -> list[str]:
        """Собирает темы статей и дополнительных материалов для антиповтора.

        Args:
            channel_id: Канал.
            exclude_id: Текущий черновик.

        Returns:
            Недавние заголовки и тексты.
        """
        articles = await self.session.scalars(
            select(ProcessedPost.article_title)
            .where(
                ProcessedPost.channel_id == channel_id,
                ProcessedPost.article_title.is_not(None),
            )
            .order_by(ProcessedPost.id.desc())
            .limit(HISTORY_LIMIT)
        )
        extras = await self.session.scalars(
            select(SupplementDraft.title)
            .where(
                SupplementDraft.channel_id == channel_id,
                SupplementDraft.id != exclude_id,
            )
            .order_by(SupplementDraft.id.desc())
            .limit(HISTORY_LIMIT)
        )
        return [title for title in [*articles, *extras] if title]
