"""Сервис публикации постов."""

from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import PostStatus, PublishStatus
from app.domain.platform_settings import _parse_bool
from app.domain.publish import PublishPermanentError
from app.infrastructure.ai.image_service import ImageService
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.models.publish_log import PublishLog
from app.infrastructure.publishers.publisher_factory import get_publisher
from app.repositories.channel_repository import ChannelRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.publish_log_repository import PublishLogRepository
from app.repositories.setting_repository import SettingRepository
from app.services.job_tracker import report_job_stage
from app.utils.hash_utils import content_hash
from app.utils.rewrite_output import is_publishable_rewrite


class PublishService:
    """Публикует approved посты в каналы."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._processed = ProcessedPostRepository(session)
        self._channels = ChannelRepository(session)
        self._settings = SettingRepository(session)
        self._logs = PublishLogRepository(session)
        self._images = ImageService()

    async def _reject(self, post: ProcessedPost, reason: str) -> None:
        """Отклоняет пост, чтобы он не завис в «Одобренных» после провала проверки.

        Args:
            post: пост, не прошедший проверку перед публикацией.
            reason: причина отклонения.
        """
        post.status = PostStatus.REJECTED.value
        post.rejection_reason = reason
        await self._processed.update(post)
        await self._session.commit()

    async def publish_post(
        self,
        post_id: int,
        *,
        celery_task_id: str | None = None,
        bypass_daily_limit: bool = False,
    ) -> PublishLog:
        """Публикует пост на платформу канала.

        Args:
            post_id: ID processed_post.
            celery_task_id: ID Celery-задачи для поэтапных уведомлений UI.
            bypass_daily_limit: не проверять дневной лимит канала — используется
                умной публикацией, где за интервал и так выбирается 1 материал
                на тему.

        Returns:
            PublishLog: запись лога.

        Raises:
            ValueError: пост не найден, лимит исчерпан или дубликат.
            PublishPermanentError: рерайт не прошёл проверку формата.
            RuntimeError: ошибка публикации.
        """
        await report_job_stage(celery_task_id, "Подготовка публикации…", 25)
        post = await self._processed.get_by_id(post_id)
        if not post:
            msg = f"Post {post_id} not found"
            raise ValueError(msg)

        if post.status not in (
            PostStatus.APPROVED.value,
            PostStatus.FAILED.value,
        ):
            msg = f"Post {post_id} cannot be published (status={post.status})"
            raise ValueError(msg)

        if post.status == PostStatus.FAILED.value:
            post.status = PostStatus.APPROVED.value
            await self._processed.update(post)

        channel = await self._channels.get_by_id(post.channel_id)
        if not channel:
            msg = f"Channel {post.channel_id} not found"
            raise ValueError(msg)

        if not bypass_daily_limit:
            posts_per_day = int(await self._settings.get("posts_per_day", "10"))
            published_today = await self._processed.count_published_today(channel.id)
            if published_today >= posts_per_day:
                msg = f"Daily limit reached for channel {channel.id}"
                await self._reject(post, f"Дневной лимит канала «{channel.name}» исчерпан")
                raise ValueError(msg)

        if not post.article_body and not is_publishable_rewrite(post.rewritten_text):
            msg = (
                f"Post {post_id} blocked: rewrite looks like model reasoning, not HTML"
            )
            logger.error(msg, channel_id=channel.id, preview=post.rewritten_text[:200])
            await self._reject(
                post, "Рерайт не прошёл проверку формата (похоже на рассуждения модели)"
            )
            raise PublishPermanentError(msg)

        text_hash = content_hash(
            post.rewritten_text + (post.article_body or "") + (post.telegraph_url or "")
        )
        if await self._processed.exists_by_hash(channel.id, text_hash):
            msg = "Duplicate content already published"
            await self._reject(post, "Дубликат: такой текст уже публиковался в этом канале")
            raise ValueError(msg)

        video_bytes = None
        image_bytes = None
        if post.generated_video_url or post.generated_image_url:
            await report_job_stage(
                celery_task_id, "Загрузка медиа для публикации…", 45
            )
        animation_enabled = _parse_bool(
            await self._settings.get("postcard_animation_enabled", "true"), True
        )
        channel_animates = getattr(channel, "animate_postcards", False)
        if (
            post.generated_video_url
            and animation_enabled
            and channel_animates
        ):
            video_bytes = await self._images.download_media_bytes(
                post.generated_video_url
            )
        if post.generated_image_url:
            image_bytes = await self._images.download_and_resize(
                post.generated_image_url
            )

        publisher = get_publisher(channel)
        log = PublishLog(
            processed_post_id=post_id,
            channel_id=channel.id,
            status=PublishStatus.FAILED.value,
        )

        try:
            await report_job_stage(
                celery_task_id,
                f"Отправка в {channel.name}…",
                72,
            )
            platform_post_id = await publisher.publish(
                post, channel, image_bytes, video_bytes=video_bytes
            )
            log.status = PublishStatus.SUCCESS.value
            log.platform_post_id = platform_post_id
            post.status = PostStatus.PUBLISHED.value
            post.published_at = datetime.now(UTC)
            post.publish_text_hash = text_hash
        except PublishPermanentError as exc:
            log.error_message = str(exc)
            post.status = PostStatus.FAILED.value
            logger.error("Publish failed (permanent)", post_id=post_id, error=str(exc))
            await self._processed.update(post)
            await self._logs.create(log)
            await self._session.commit()
            raise
        except Exception as exc:
            log.error_message = str(exc)
            post.status = PostStatus.FAILED.value
            logger.error("Publish failed", post_id=post_id, error=str(exc))
            await self._processed.update(post)
            await self._logs.create(log)
            await self._session.commit()
            raise RuntimeError(str(exc)) from exc

        await self._processed.update(post)
        saved_log = await self._logs.create(log)
        await self._session.commit()

        return saved_log
