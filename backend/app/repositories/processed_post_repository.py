"""Репозиторий обработанных постов."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.domain.enums import PostStatus
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.models.raw_post import RawPost


class ProcessedPostRepository:
    """CRUD для processed_posts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_queue(self) -> list[ProcessedPost]:
        """Очередь pending.

        Returns:
            list[ProcessedPost]: посты в очереди.
        """
        result = await self._session.execute(
            select(ProcessedPost)
            .where(ProcessedPost.status == PostStatus.PENDING.value)
            .options(
                joinedload(ProcessedPost.raw_post),
                joinedload(ProcessedPost.channel),
            )
            .order_by(ProcessedPost.created_at.desc())
        )
        return list(result.scalars().unique().all())

    async def list_pending_ids_for_bulk(
        self,
        *,
        post_ids: list[int] | None = None,
        channel_id: int | None = None,
        topic: str | None = None,
        older_than_days: int | None = None,
        limit: int = 2000,
    ) -> list[int]:
        """ID pending-постов для массовых операций.

        Args:
            post_ids: ограничить конкретными ID.
            channel_id: фильтр по каналу.
            topic: фильтр по теме сырого поста.
            older_than_days: посты старше N дней.
            limit: максимум записей за один запрос.

        Returns:
            list[int]: подходящие ID.
        """
        query = select(ProcessedPost.id).where(
            ProcessedPost.status == PostStatus.PENDING.value
        )
        if post_ids:
            query = query.where(ProcessedPost.id.in_(post_ids))
        if channel_id is not None:
            query = query.where(ProcessedPost.channel_id == channel_id)
        if topic is not None:
            query = query.join(
                RawPost, ProcessedPost.raw_post_id == RawPost.id
            ).where(RawPost.topic == topic)
        if older_than_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
            query = query.where(ProcessedPost.created_at <= cutoff)
        query = query.order_by(ProcessedPost.created_at.desc()).limit(limit)
        result = await self._session.execute(query)
        return [int(row[0]) for row in result.all()]

    async def count_pending_for_bulk(
        self,
        *,
        channel_id: int | None = None,
        topic: str | None = None,
        older_than_days: int | None = None,
    ) -> int:
        """Счётчик pending-постов по фильтрам.

        Returns:
            int: количество постов.
        """
        ids = await self.list_pending_ids_for_bulk(
            channel_id=channel_id,
            topic=topic,
            older_than_days=older_than_days,
            limit=2000,
        )
        return len(ids)

    async def list_approved(self) -> list[ProcessedPost]:
        """Очередь публикации: одобренные и посты с ошибкой публикации.

        Returns:
            list[ProcessedPost]: посты approved и failed (для повтора).
        """
        result = await self._session.execute(
            select(ProcessedPost)
            .where(
                ProcessedPost.status.in_(
                    (PostStatus.APPROVED.value, PostStatus.FAILED.value)
                )
            )
            .options(
                joinedload(ProcessedPost.raw_post),
                joinedload(ProcessedPost.channel),
            )
            .order_by(
                ProcessedPost.status.desc(),
                ProcessedPost.scheduled_at.asc().nulls_last(),
                ProcessedPost.updated_at.desc(),
            )
        )
        return list(result.scalars().unique().all())

    async def count_approved(self) -> int:
        """Количество постов в очереди публикации.

        Returns:
            int: счётчик approved + failed.
        """
        result = await self._session.execute(
            select(func.count(ProcessedPost.id)).where(
                ProcessedPost.status.in_(
                    (PostStatus.APPROVED.value, PostStatus.FAILED.value)
                )
            )
        )
        return int(result.scalar_one())

    async def count_by_status(self, status: PostStatus) -> int:
        """Количество постов с указанным статусом.

        Args:
            status: статус processed_post.

        Returns:
            int: счётчик.
        """
        result = await self._session.execute(
            select(func.count(ProcessedPost.id)).where(
                ProcessedPost.status == status.value
            )
        )
        return int(result.scalar_one())

    async def list_upcoming_scheduled(self, *, limit: int = 5) -> list[ProcessedPost]:
        """Одобренные посты с будущим scheduled_at.

        Args:
            limit: максимум записей.

        Returns:
            list[ProcessedPost]: посты от ближайших к дальним.
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ProcessedPost)
            .where(
                ProcessedPost.status == PostStatus.APPROVED.value,
                ProcessedPost.scheduled_at.isnot(None),
                ProcessedPost.scheduled_at > now,
            )
            .options(joinedload(ProcessedPost.channel))
            .order_by(ProcessedPost.scheduled_at.asc())
            .limit(limit)
        )
        return list(result.scalars().unique().all())

    async def list_approved_by_channel(self, channel_id: int) -> list[ProcessedPost]:
        """Одобренные посты канала по порядку создания.

        Args:
            channel_id: ID канала.

        Returns:
            list[ProcessedPost]: посты для пересчёта расписания.
        """
        result = await self._session.execute(
            select(ProcessedPost)
            .where(
                ProcessedPost.channel_id == channel_id,
                ProcessedPost.status == PostStatus.APPROVED.value,
            )
            .order_by(ProcessedPost.created_at.asc())
        )
        return list(result.scalars().all())

    async def get_last_scheduled_for_channel(
        self, channel_id: int
    ) -> datetime | None:
        """Последний запланированный слот на канале.

        Args:
            channel_id: ID канала.

        Returns:
            datetime | None: максимальный scheduled_at.
        """
        result = await self._session.execute(
            select(func.max(ProcessedPost.scheduled_at)).where(
                ProcessedPost.channel_id == channel_id,
                ProcessedPost.status == PostStatus.APPROVED.value,
                ProcessedPost.scheduled_at.isnot(None),
            )
        )
        value = result.scalar_one_or_none()
        return value if isinstance(value, datetime) else None

    async def delete_by_id(self, post_id: int) -> bool:
        """Удаляет processed_post.

        Args:
            post_id: ID поста.

        Returns:
            bool: True если запись удалена.
        """
        result = await self._session.execute(
            sa_delete(ProcessedPost).where(ProcessedPost.id == post_id)
        )
        return (result.rowcount or 0) > 0

    async def get_by_id(self, post_id: int) -> ProcessedPost | None:
        """Пост с связями.

        Args:
            post_id: ID.

        Returns:
            ProcessedPost | None: модель.
        """
        result = await self._session.execute(
            select(ProcessedPost)
            .where(ProcessedPost.id == post_id)
            .options(
                joinedload(ProcessedPost.raw_post),
                joinedload(ProcessedPost.channel),
            )
        )
        return result.scalar_one_or_none()

    async def create(self, post: ProcessedPost) -> ProcessedPost:
        """Создаёт обработанный пост.

        Args:
            post: модель.

        Returns:
            ProcessedPost: сохранённый пост.
        """
        self._session.add(post)
        await self._session.flush()
        await self._session.refresh(post)
        return post

    async def update(self, post: ProcessedPost) -> ProcessedPost:
        """Обновляет пост.

        Args:
            post: модель.

        Returns:
            ProcessedPost: обновлённый пост.
        """
        post.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(post)
        return post

    async def count_published_today(self, channel_id: int) -> int:
        """Количество публикаций за сегодня на канал.

        Args:
            channel_id: ID канала.

        Returns:
            int: число публикаций.
        """
        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = await self._session.execute(
            select(func.count(ProcessedPost.id)).where(
                ProcessedPost.channel_id == channel_id,
                ProcessedPost.status == PostStatus.PUBLISHED.value,
                ProcessedPost.published_at >= today_start,
            )
        )
        return int(result.scalar_one())

    async def list_recent_article_titles(
        self,
        channel_id: int,
        *,
        limit: int = 30,
        days: int = 30,
    ) -> list[str]:
        """Возвращает недавние заголовки статей канала для антиповтора тем.

        Учитывает pending, approved, published и failed — всё, кроме rejected.

        Args:
            channel_id: ID канала.
            limit: максимум заголовков.
            days: глубина поиска в днях.

        Returns:
            list[str]: заголовки от новых к старым.
        """
        from app.domain.enums import ContentMode

        since = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            select(ProcessedPost.article_title)
            .where(
                ProcessedPost.channel_id == channel_id,
                ProcessedPost.content_mode == ContentMode.ARTICLE.value,
                ProcessedPost.status != PostStatus.REJECTED.value,
                ProcessedPost.article_title.isnot(None),
                ProcessedPost.created_at >= since,
            )
            .order_by(ProcessedPost.created_at.desc())
            .limit(limit)
        )
        return [str(title).strip() for title in result.scalars().all() if title]

    async def list_recent_article_teasers(
        self,
        channel_id: int,
        *,
        limit: int = 12,
        days: int = 30,
    ) -> list[str]:
        """Возвращает недавние анонсы статей канала (rewritten_text).

        Args:
            channel_id: ID канала.
            limit: максимум анонсов.
            days: глубина поиска в днях.

        Returns:
            list[str]: HTML анонсов от новых к старым.
        """
        from app.domain.enums import ContentMode

        since = datetime.now(UTC) - timedelta(days=days)
        result = await self._session.execute(
            select(ProcessedPost.rewritten_text)
            .where(
                ProcessedPost.channel_id == channel_id,
                ProcessedPost.content_mode == ContentMode.ARTICLE.value,
                ProcessedPost.status != PostStatus.REJECTED.value,
                ProcessedPost.rewritten_text.isnot(None),
                ProcessedPost.created_at >= since,
            )
            .order_by(ProcessedPost.created_at.desc())
            .limit(limit)
        )
        return [str(text).strip() for text in result.scalars().all() if text]

    async def count_articles_created_today(self, channel_id: int) -> int:
        """Количество сгенерированных статей за сегодня (кроме rejected).

        Args:
            channel_id: ID канала.

        Returns:
            int: число статей.
        """
        from app.domain.enums import ContentMode

        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        result = await self._session.execute(
            select(func.count(ProcessedPost.id)).where(
                ProcessedPost.channel_id == channel_id,
                ProcessedPost.content_mode == ContentMode.ARTICLE.value,
                ProcessedPost.status != PostStatus.REJECTED.value,
                ProcessedPost.created_at >= today_start,
            )
        )
        return int(result.scalar_one())

    async def list_scheduled_due(self) -> list[ProcessedPost]:
        """Посты approved с наступившим scheduled_at.

        Returns:
            list[ProcessedPost]: посты к публикации.
        """
        now = datetime.now(UTC)
        result = await self._session.execute(
            select(ProcessedPost)
            .where(
                ProcessedPost.status == PostStatus.APPROVED.value,
                ProcessedPost.scheduled_at.isnot(None),
                ProcessedPost.scheduled_at <= now,
            )
            .options(joinedload(ProcessedPost.channel))
        )
        return list(result.scalars().unique().all())

    async def exists_by_hash(self, channel_id: int, text_hash: str) -> bool:
        """Проверка дубликата публикации по хешу текста.

        Args:
            channel_id: ID канала.
            text_hash: хеш текста.

        Returns:
            bool: True если уже публиковали.
        """
        result = await self._session.execute(
            select(ProcessedPost.id).where(
                ProcessedPost.channel_id == channel_id,
                ProcessedPost.publish_text_hash == text_hash,
                ProcessedPost.status == PostStatus.PUBLISHED.value,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_history(
        self,
        channel_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ProcessedPost]:
        """История опубликованных постов.

        Args:
            channel_id: фильтр по каналу.
            limit: лимит.
            offset: смещение.

        Returns:
            list[ProcessedPost]: история.
        """
        query = (
            select(ProcessedPost)
            .where(ProcessedPost.status == PostStatus.PUBLISHED.value)
            .options(
                joinedload(ProcessedPost.channel),
                joinedload(ProcessedPost.raw_post),
            )
            .order_by(ProcessedPost.published_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if channel_id:
            query = query.where(ProcessedPost.channel_id == channel_id)
        result = await self._session.execute(query)
        return list(result.scalars().unique().all())
