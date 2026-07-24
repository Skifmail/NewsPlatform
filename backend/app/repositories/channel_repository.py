"""Репозиторий каналов."""

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ContentMode
from app.infrastructure.models.channel import Channel


class ChannelRepository:
    """CRUD для channels."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Channel]:
        """Все каналы.

        Returns:
            list[Channel]: каналы.
        """
        result = await self._session.execute(
            select(Channel).order_by(Channel.id)
        )
        return list(result.scalars().all())

    async def list_active_by_topic(self, topic: str) -> list[Channel]:
        """Активные каналы по тематике.

        Args:
            topic: тематика.

        Returns:
            list[Channel]: каналы.
        """
        result = await self._session.execute(
            select(Channel).where(
                Channel.is_active.is_(True),
                Channel.topic == topic,
                Channel.content_mode == ContentMode.NEWS.value,
            )
        )
        return list(result.scalars().all())

    async def list_active(self) -> list[Channel]:
        """Все активные каналы независимо от content_mode.

        Returns:
            list[Channel]: каналы, у которых is_active=True.
        """
        result = await self._session.execute(
            select(Channel).where(Channel.is_active.is_(True)).order_by(Channel.id)
        )
        return list(result.scalars().all())

    async def list_active_article_channels(self) -> list[Channel]:
        """Активные каналы в режиме статей.

        Returns:
            list[Channel]: article-каналы.
        """
        result = await self._session.execute(
            select(Channel).where(
                Channel.is_active.is_(True),
                Channel.content_mode == ContentMode.ARTICLE.value,
            )
        )
        return list(result.scalars().all())

    async def get_by_id(self, channel_id: int) -> Channel | None:
        """Канал по ID.

        Args:
            channel_id: идентификатор.

        Returns:
            Channel | None: модель.
        """
        return await self._session.get(Channel, channel_id)

    async def create(self, channel: Channel) -> Channel:
        """Создаёт канал.

        Args:
            channel: модель.

        Returns:
            Channel: сохранённый канал.
        """
        self._session.add(channel)
        await self._session.flush()
        await self._session.refresh(channel)
        return channel

    async def update(self, channel: Channel) -> Channel:
        """Обновляет канал.

        Args:
            channel: модель.

        Returns:
            Channel: обновлённый канал.
        """
        await self._session.flush()
        await self._session.refresh(channel)
        return channel

    async def delete(self, channel: Channel) -> None:
        """Удаляет канал и связанные записи (каскад в БД).

        Args:
            channel: модель.
        """
        await self._session.execute(
            delete(Channel).where(Channel.id == channel.id)
        )
        await self._session.flush()
