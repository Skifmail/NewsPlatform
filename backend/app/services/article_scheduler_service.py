"""Планировщик автогенерации статей для article-каналов."""

from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.article import article_scheduler_key
from app.domain.enums import ContentMode
from app.repositories.channel_repository import ChannelRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.setting_repository import SettingRepository
from app.services.job_tracker import JobTracker
from app.services.platform_settings_service import PlatformSettingsService
from app.services.scheduling_service import SchedulingService
from app.tasks.article_tasks import generate_article_task


class ArticleSchedulerService:
    """Запускает генерацию статей по расписанию каналов."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._channels = ChannelRepository(session)
        self._processed = ProcessedPostRepository(session)
        self._settings = SettingRepository(session)
        self._platform = PlatformSettingsService(session)
        self._scheduling = SchedulingService(session)
        self._jobs = JobTracker(session)

    async def run_due_channels(self) -> dict[int, int | None]:
        """Ставит в очередь генерацию для каналов, у которых наступил слот.

        Returns:
            dict[int, int | None]: channel_id → processed_post_id или None.
        """
        platform = await self._platform.load()
        if not platform.schedule_article_publish_enabled:
            return {}

        now = datetime.now(UTC)
        result: dict[int, int | None] = {}
        channels = await self._channels.list_active_article_channels()
        for channel in channels:
            post_id = await self._try_channel(
                channel=channel,
                now=now,
                posts_per_day=platform.posts_per_day,
            )
            result[channel.id] = post_id
        return result

    async def _try_channel(
        self,
        *,
        channel: object,
        now: datetime,
        posts_per_day: int,
    ) -> int | None:
        """Пытается поставить генерацию статьи для одного канала.

        Args:
            channel: модель Channel.
            now: текущий момент UTC.
            posts_per_day: лимит публикаций на канал в сутки.

        Returns:
            int | None: None если слот не наступил (задача в очереди).
        """
        from app.infrastructure.models.channel import Channel

        if not isinstance(channel, Channel):
            return None

        if not self._scheduling._in_publish_window(now, channel):
            return None

        published_today = await self._processed.count_published_today(channel.id)
        created_today = await self._processed.count_articles_created_today(channel.id)
        if published_today >= posts_per_day or created_today >= posts_per_day:
            logger.info(
                "Article skipped: daily limit",
                channel_id=channel.id,
                published_today=published_today,
                created_today=created_today,
            )
            return None

        interval = max(1, channel.publish_interval_minutes)
        last_key = article_scheduler_key(channel.id)
        last_raw = (await self._settings.get(last_key, "")).strip()
        if last_raw:
            try:
                last_at = datetime.fromisoformat(last_raw)
                if now - last_at < timedelta(minutes=interval):
                    return None
            except ValueError:
                pass

        celery_result = generate_article_task.delay(channel.id)
        await self._jobs.enqueue_article(
            celery_result.id,
            channel.id,
            channel.name,
        )
        await self._settings.set(last_key, now.isoformat())
        await self._session.commit()

        logger.info(
            "Article generation queued",
            channel_id=channel.id,
            celery_task_id=celery_result.id,
        )
        return None
