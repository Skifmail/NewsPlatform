"""Репозиторий лога публикаций."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.models.publish_log import PublishLog


class PublishLogRepository:
    """CRUD для publish_log."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def map_latest_by_posts(
        self, post_ids: list[int]
    ) -> dict[int, PublishLog]:
        """Возвращает последнюю попытку публикации для каждого поста.

        Args:
            post_ids: ID processed_posts.

        Returns:
            dict[int, PublishLog]: post_id → последняя запись лога.
        """
        if not post_ids:
            return {}
        result = await self._session.execute(
            select(PublishLog)
            .where(PublishLog.processed_post_id.in_(post_ids))
            .order_by(PublishLog.published_at.desc())
        )
        latest: dict[int, PublishLog] = {}
        for log in result.scalars().all():
            if log.processed_post_id is None:
                continue
            if log.processed_post_id not in latest:
                latest[log.processed_post_id] = log
        return latest

    async def list_history(
        self,
        channel_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[PublishLog]:
        """История всех попыток публикации (успех и ошибки).

        Args:
            channel_id: фильтр по каналу.
            limit: лимит.
            offset: смещение.

        Returns:
            list[PublishLog]: записи от новых к старым.
        """
        query = (
            select(PublishLog)
            .options(
                joinedload(PublishLog.processed_post).joinedload(
                    ProcessedPost.channel
                )
            )
            .order_by(PublishLog.published_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if channel_id is not None:
            query = query.where(PublishLog.channel_id == channel_id)
        result = await self._session.execute(query)
        return list(result.scalars().unique().all())

    async def create(self, log: PublishLog) -> PublishLog:
        """Создаёт запись лога.

        Args:
            log: модель.

        Returns:
            PublishLog: сохранённая запись.
        """
        self._session.add(log)
        await self._session.flush()
        await self._session.refresh(log)
        return log

    async def list_successful_by_channel(
        self,
        channel_id: int,
        *,
        limit: int = 100,
    ) -> list[PublishLog]:
        """Успешные публикации канала с platform_post_id.

        Args:
            channel_id: ID канала.
            limit: максимум записей.

        Returns:
            list[PublishLog]: логи от новых к старым.
        """
        from app.domain.enums import PublishStatus

        result = await self._session.execute(
            select(PublishLog)
            .where(
                PublishLog.channel_id == channel_id,
                PublishLog.status == PublishStatus.SUCCESS.value,
                PublishLog.platform_post_id.is_not(None),
            )
            .order_by(PublishLog.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_successful_by_channel(self, channel_id: int) -> int:
        """Число успешных публикаций канала из нашей платформы.

        Args:
            channel_id: ID канала.

        Returns:
            int: количество.
        """
        from app.domain.enums import PublishStatus
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count(PublishLog.id)).where(
                PublishLog.channel_id == channel_id,
                PublishLog.status == PublishStatus.SUCCESS.value,
            )
        )
        return int(result.scalar_one() or 0)

    async def count_successful_all(self) -> int:
        """Общее число успешных публикаций.

        Returns:
            int: количество.
        """
        from app.domain.enums import PublishStatus
        from sqlalchemy import func

        result = await self._session.execute(
            select(func.count(PublishLog.id)).where(
                PublishLog.status == PublishStatus.SUCCESS.value,
            )
        )
        return int(result.scalar_one() or 0)

    async def count_since_grouped_by_status(
        self, since: datetime
    ) -> dict[str, int]:
        """Считает попытки публикации с момента since по статусу.

        Args:
            since: нижняя граница published_at (UTC).

        Returns:
            dict[str, int]: статус → количество.
        """
        from sqlalchemy import func

        result = await self._session.execute(
            select(PublishLog.status, func.count(PublishLog.id))
            .where(PublishLog.published_at >= since)
            .group_by(PublishLog.status)
        )
        return {str(row[0]): int(row[1]) for row in result.all()}
