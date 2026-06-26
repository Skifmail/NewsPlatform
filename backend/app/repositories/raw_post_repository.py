"""Репозиторий сырых постов."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.enums import PostStatus, Topic
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.models.raw_post import RawPost
from app.infrastructure.models.source import Source


class RawPostRepository:
    """CRUD для raw_posts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(
        self, source_id: int, external_id: str | None
    ) -> bool:
        """Проверяет дубликат по external_id.

        Args:
            source_id: ID источника.
            external_id: внешний ID.

        Returns:
            bool: True если уже есть.
        """
        if not external_id:
            return False
        result = await self._session.execute(
            select(RawPost.id).where(
                RawPost.source_id == source_id,
                RawPost.external_id == external_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def create(self, post: RawPost) -> RawPost:
        """Создаёт сырой пост.

        Args:
            post: модель.

        Returns:
            RawPost: сохранённый пост.
        """
        self._session.add(post)
        await self._session.flush()
        await self._session.refresh(post)
        return post

    async def get_by_id(self, post_id: int) -> RawPost | None:
        """Пост по ID.

        Args:
            post_id: идентификатор.

        Returns:
            RawPost | None: модель.
        """
        return await self._session.get(RawPost, post_id)

    async def list_filtered(
        self,
        *,
        source_id: int | None = None,
        topic: Topic | None = None,
        is_processed: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[RawPost]:
        """Список сырых постов с фильтрами.

        Args:
            source_id: фильтр по источнику.
            topic: фильтр по теме.
            is_processed: фильтр по статусу AI.
            limit: размер страницы.
            offset: смещение.

        Returns:
            list[RawPost]: посты с подгруженным source.
        """
        query = (
            select(RawPost)
            .options(selectinload(RawPost.source))
            .order_by(RawPost.fetched_at.desc())
            .limit(min(limit, 200))
            .offset(offset)
        )
        if source_id is not None:
            query = query.where(RawPost.source_id == source_id)
        if topic is not None:
            query = query.where(RawPost.topic == topic.value)
        if is_processed is not None:
            query = query.where(RawPost.is_processed == is_processed)
        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def count_filtered(
        self,
        *,
        source_id: int | None = None,
        is_processed: bool | None = None,
    ) -> int:
        """Число постов по фильтрам.

        Args:
            source_id: фильтр по источнику.
            is_processed: фильтр по статусу AI.

        Returns:
            int: количество записей.
        """
        query = select(func.count(RawPost.id))
        if source_id is not None:
            query = query.where(RawPost.source_id == source_id)
        if is_processed is not None:
            query = query.where(RawPost.is_processed == is_processed)
        result = await self._session.execute(query)
        return int(result.scalar_one())

    async def count_filtered_extended(
        self,
        *,
        source_id: int | None = None,
        topic: Topic | None = None,
        is_processed: bool | None = None,
        older_than_days: int | None = None,
        exclude_published_children: bool = True,
    ) -> tuple[int, int]:
        """Счётчик постов для массового удаления.

        Returns:
            tuple[int, int]: (можно удалить, пропустить из-за публикации).
        """
        deletable, skipped = await self.list_ids_for_bulk_delete(
            source_id=source_id,
            topic=topic,
            is_processed=is_processed,
            older_than_days=older_than_days,
            exclude_published_children=exclude_published_children,
            limit=2000,
        )
        return len(deletable), len(skipped)

    async def list_ids_for_bulk_delete(
        self,
        *,
        raw_post_ids: list[int] | None = None,
        source_id: int | None = None,
        topic: Topic | None = None,
        is_processed: bool | None = None,
        older_than_days: int | None = None,
        exclude_published_children: bool = True,
        limit: int = 2000,
    ) -> tuple[list[int], list[int]]:
        """Список ID сырых постов для удаления и пропущенных.

        Returns:
            tuple[list[int], list[int]]: (deletable_ids, skipped_ids).
        """
        query = select(RawPost.id).order_by(RawPost.fetched_at.desc()).limit(limit)
        if raw_post_ids:
            query = query.where(RawPost.id.in_(raw_post_ids))
        if source_id is not None:
            query = query.where(RawPost.source_id == source_id)
        if topic is not None:
            query = query.where(RawPost.topic == topic.value)
        if is_processed is not None:
            query = query.where(RawPost.is_processed == is_processed)
        if older_than_days is not None:
            cutoff = datetime.now(UTC) - timedelta(days=older_than_days)
            query = query.where(RawPost.fetched_at <= cutoff)

        result = await self._session.execute(query)
        candidate_ids = [int(row[0]) for row in result.all()]
        if not candidate_ids or not exclude_published_children:
            return candidate_ids, []

        skipped_result = await self._session.execute(
            select(ProcessedPost.raw_post_id)
            .where(
                ProcessedPost.raw_post_id.in_(candidate_ids),
                ProcessedPost.status == PostStatus.PUBLISHED.value,
            )
            .distinct()
        )
        skipped_ids = {
            int(row[0]) for row in skipped_result.all() if row[0] is not None
        }
        deletable = [pid for pid in candidate_ids if pid not in skipped_ids]
        return deletable, sorted(skipped_ids)

    async def delete_by_ids(self, raw_post_ids: list[int]) -> int:
        """Удаляет сырые посты по ID.

        Returns:
            int: число удалённых записей.
        """
        if not raw_post_ids:
            return 0
        result = await self._session.execute(
            sa_delete(RawPost).where(RawPost.id.in_(raw_post_ids))
        )
        return int(result.rowcount or 0)

    async def stats_by_source(self) -> list[tuple[int, str, str, int, int]]:
        """Агрегаты по каждому источнику.

        Returns:
            list[tuple]: source_id, name, topic, total, unprocessed.
        """
        total_expr = func.count(RawPost.id)
        unprocessed_expr = func.count(RawPost.id).filter(
            RawPost.is_processed.is_(False)
        )
        result = await self._session.execute(
            select(
                Source.id,
                Source.name,
                Source.topic,
                total_expr,
                unprocessed_expr,
            )
            .outerjoin(RawPost, RawPost.source_id == Source.id)
            .group_by(Source.id, Source.name, Source.topic)
            .order_by(Source.name)
        )
        return [
            (int(row[0]), str(row[1]), str(row[2]), int(row[3]), int(row[4]))
            for row in result.all()
        ]

    async def count_processed_children(self, raw_post_id: int) -> int:
        """Число processed_posts, созданных из сырого поста.

        Args:
            raw_post_id: ID raw_post.

        Returns:
            int: количество записей.
        """
        result = await self._session.execute(
            select(func.count(ProcessedPost.id)).where(
                ProcessedPost.raw_post_id == raw_post_id
            )
        )
        return int(result.scalar_one())

    async def unmark_processed(self, post_id: int) -> None:
        """Снимает флаг обработки (для повторного AI).

        Args:
            post_id: ID поста.
        """
        post = await self.get_by_id(post_id)
        if post:
            post.is_processed = False
            await self._session.flush()

    async def mark_processed(self, post_id: int) -> None:
        """Помечает пост обработанным.

        Args:
            post_id: ID поста.
        """
        post = await self.get_by_id(post_id)
        if post:
            post.is_processed = True
            await self._session.flush()

    async def count_unprocessed(self) -> int:
        """Число сырых материалов без AI-обработки.

        Returns:
            int: количество необработанных raw_posts.
        """
        result = await self._session.execute(
            select(func.count(RawPost.id)).where(RawPost.is_processed.is_(False))
        )
        return int(result.scalar_one())
