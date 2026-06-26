"""Репозиторий метрик постов."""

from sqlalchemy import asc, desc, func, nullslast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.infrastructure.models.post_metric import PostMetric

POST_METRIC_SORT_FIELDS = frozenset(
    {"views", "published_at", "reactions", "forwards", "comments", "reach"}
)


class PostMetricsRepository:
    """CRUD для post_metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, metric: PostMetric) -> PostMetric:
        """Создаёт или обновляет метрики поста.

        Args:
            metric: модель метрик.

        Returns:
            PostMetric: сохранённая запись.
        """
        result = await self._session.execute(
            select(PostMetric).where(
                PostMetric.channel_id == metric.channel_id,
                PostMetric.platform_post_id == metric.platform_post_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.processed_post_id = (
                metric.processed_post_id or existing.processed_post_id
            )
            existing.publish_log_id = metric.publish_log_id or existing.publish_log_id
            existing.post_url = metric.post_url or existing.post_url
            existing.views = metric.views if metric.views is not None else existing.views
            existing.forwards = (
                metric.forwards if metric.forwards is not None else existing.forwards
            )
            existing.reactions = (
                metric.reactions if metric.reactions is not None else existing.reactions
            )
            existing.comments = (
                metric.comments if metric.comments is not None else existing.comments
            )
            existing.reach = metric.reach if metric.reach is not None else existing.reach
            if metric.published_at is not None:
                existing.published_at = metric.published_at
            existing.collected_at = metric.collected_at
            await self._session.flush()
            await self._session.refresh(existing)
            return existing

        self._session.add(metric)
        await self._session.flush()
        await self._session.refresh(metric)
        return metric

    async def list_for_channel(
        self,
        channel_id: int,
        *,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "published_at",
        sort_order: str = "desc",
    ) -> list[PostMetric]:
        """Метрики постов канала.

        Args:
            channel_id: ID канала.
            limit: лимит.
            offset: смещение.
            sort_by: поле сортировки.
            sort_order: asc | desc.

        Returns:
            list[PostMetric]: метрики постов.

        Raises:
            ValueError: неизвестное поле сортировки.
        """
        if sort_by not in POST_METRIC_SORT_FIELDS:
            msg = f"Invalid sort field: {sort_by}"
            raise ValueError(msg)
        if sort_order not in {"asc", "desc"}:
            msg = f"Invalid sort order: {sort_order}"
            raise ValueError(msg)

        sort_column = getattr(PostMetric, sort_by)
        order_expr = (
            nullslast(desc(sort_column))
            if sort_order == "desc"
            else nullslast(asc(sort_column))
        )

        result = await self._session.execute(
            select(PostMetric)
            .options(joinedload(PostMetric.processed_post))
            .where(PostMetric.channel_id == channel_id)
            .order_by(order_expr, PostMetric.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().unique().all())

    async def aggregate_for_channel(self, channel_id: int) -> dict[str, float | int | None]:
        """Средние и суммарные метрики по каналу.

        Args:
            channel_id: ID канала.

        Returns:
            dict: avg_views, total_views, posts_with_views, avg_reach, posts_with_metrics.
        """
        result = await self._session.execute(
            select(
                func.avg(PostMetric.views),
                func.sum(PostMetric.views),
                func.count(PostMetric.views),
                func.avg(PostMetric.reach),
                func.count(PostMetric.id),
            ).where(PostMetric.channel_id == channel_id)
        )
        avg_views, total_views, posts_with_views, avg_reach, count = result.one()
        return {
            "avg_views": round(float(avg_views), 1) if avg_views is not None else None,
            "total_views": int(total_views) if total_views is not None else None,
            "posts_with_views": int(posts_with_views or 0),
            "avg_reach": round(float(avg_reach), 1) if avg_reach is not None else None,
            "posts_with_metrics": int(count or 0),
        }
