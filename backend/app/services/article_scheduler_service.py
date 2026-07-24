"""Единый планировщик публикаций каналов по publish_times (МСК).

При наступлении слота:
- news-канал  → берётся самый старый approved-пост из очереди и публикуется;
- article-канал → запускается генерация статьи (публикация происходит в задаче).
"""

from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.article import article_scheduler_key
from app.domain.article_schedule import due_slot
from app.domain.enums import ContentMode
from app.infrastructure.models.channel import Channel
from app.repositories.channel_repository import ChannelRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.setting_repository import SettingRepository
from app.services.job_tracker import JobTracker
from app.services.platform_settings_service import PlatformSettingsService
from app.tasks.article_tasks import generate_article_task
from app.tasks.publish_tasks import publish_post_task


class ArticleSchedulerService:
    """Планировщик публикаций для всех активных каналов по publish_times."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._channels = ChannelRepository(session)
        self._processed = ProcessedPostRepository(session)
        self._settings = SettingRepository(session)
        self._platform = PlatformSettingsService(session)
        self._jobs = JobTracker(session)

    async def run_due_channels(self) -> dict[int, int | None]:
        """Ставит в очередь публикацию для каналов, у которых наступил слот.

        Returns:
            dict[int, int | None]: channel_id → post_id или None.
        """
        platform = await self._platform.load()
        article_enabled = platform.schedule_article_publish_enabled
        news_enabled = platform.schedule_publish_enabled

        now = datetime.now(UTC)
        result: dict[int, int | None] = {}
        channels = await self._channels.list_active()
        for channel in channels:
            if channel.content_mode == ContentMode.ARTICLE.value:
                if not article_enabled:
                    continue
                post_id = await self._try_article_channel(channel, now)
            else:
                if not news_enabled:
                    continue
                post_id = await self._try_news_channel(channel, now)
            result[channel.id] = post_id
        return result

    async def _slot_reached(self, channel: Channel, now: datetime) -> bool:
        """Проверяет, наступил ли новый слот и что он ещё не отрабатывал."""
        times_raw = (channel.publish_times or "").strip()
        if not times_raw:
            return False
        last_key = article_scheduler_key(channel.id)
        last_raw = (await self._settings.get(last_key, "")).strip()
        last_at: datetime | None = None
        if last_raw:
            try:
                last_at = datetime.fromisoformat(last_raw)
            except ValueError:
                last_at = None
        return due_slot(now, times_raw, last_at) is not None

    async def _mark_slot_run(self, channel_id: int, now: datetime) -> None:
        """Отмечает слот как отработанный."""
        await self._settings.set(article_scheduler_key(channel_id), now.isoformat())
        await self._session.commit()

    async def _try_article_channel(
        self, channel: Channel, now: datetime
    ) -> int | None:
        """Генерация статьи для article-канала на текущий слот."""
        if not await self._slot_reached(channel, now):
            return None

        celery_result = generate_article_task.delay(channel.id)
        await self._jobs.enqueue_article(
            celery_result.id, channel.id, channel.name,
        )
        await self._mark_slot_run(channel.id, now)
        logger.info(
            "Article generation queued",
            channel_id=channel.id,
            celery_task_id=celery_result.id,
        )
        return None

    async def _try_news_channel(
        self, channel: Channel, now: datetime
    ) -> int | None:
        """Публикация самого старого approved-поста news-канала."""
        if not await self._slot_reached(channel, now):
            return None

        post = await self._processed.get_next_approved_for_channel(channel.id)
        if post is None:
            logger.info(
                "News slot skipped: empty approved queue",
                channel_id=channel.id,
            )
            await self._mark_slot_run(channel.id, now)
            return None

        publish_post_task.delay(post.id)
        await self._mark_slot_run(channel.id, now)
        logger.info(
            "News post publish queued",
            channel_id=channel.id,
            post_id=post.id,
        )
        return post.id
