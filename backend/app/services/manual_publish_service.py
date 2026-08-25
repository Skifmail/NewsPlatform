"""Сервис ручной публикации постов из панели управления.

Callers: ``app.api.routers.posts.create_manual_post`` (POST /api/posts/manual).
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.article_meta import ArticleMeta, serialize_article_meta
from app.domain.enums import ContentMode, ImageSource, PostStatus
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.channel_repository import ChannelRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.services.job_tracker import JobTracker
from app.services.media_asset_service import MediaAssetService
from app.tasks.publish_tasks import publish_post_task


class ManualPublishService:
    """Создаёт пост вручную и опционально сразу ставит в очередь публикации."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._channels = ChannelRepository(session)
        self._processed = ProcessedPostRepository(session)

    async def create_and_publish(
        self,
        *,
        channel_id: int,
        text: str,
        button_options: list[str],
        image_url: str | None = None,
        video_url: str | None = None,
        publish_immediately: bool = True,
    ) -> ProcessedPost:
        """Создаёт processed_post и при необходимости ставит публикацию в Celery.

        Args:
            channel_id: целевой канал.
            text: HTML-текст поста.
            button_options: подписи callback-кнопок (ожидается 2).
            image_url: обложка (``local://`` или HTTP).
            video_url: видео к обложке (``local://`` или HTTP).
            publish_immediately: сразу поставить в очередь публикации.

        Returns:
            ProcessedPost: созданный пост.

        Raises:
            ValueError: канал не найден или текст пустой / кнопки не заданы.
        """
        channel = await self._channels.get_by_id(channel_id)
        if not channel:
            msg = f"Канал {channel_id} не найден"
            raise ValueError(msg)

        body = (text or "").strip()
        if not body:
            msg = "Текст поста не может быть пустым"
            raise ValueError(msg)

        cleaned_buttons = [opt.strip() for opt in button_options if opt and opt.strip()]
        if len(cleaned_buttons) < 2:
            msg = "Укажите текст обеих callback-кнопок"
            raise ValueError(msg)
        cleaned_buttons = cleaned_buttons[:2]

        meta = ArticleMeta(button_options=cleaned_buttons)
        content_mode = channel.content_mode or ContentMode.NEWS.value
        is_article = content_mode == ContentMode.ARTICLE.value

        post = ProcessedPost(
            raw_post_id=None,
            channel_id=channel.id,
            rewritten_text=body,
            content_mode=content_mode,
            article_title=None,
            article_body=body if is_article else None,
            article_meta=serialize_article_meta(meta),
            generated_image_url=image_url or None,
            generated_video_url=video_url or None,
            image_source=ImageSource.MANUAL.value,
            ai_model="manual",
            status=PostStatus.APPROVED.value,
        )
        saved = await self._processed.create(post)
        await MediaAssetService(self._session).register_from_post(
            saved, title=f"Ручной пост #{saved.id}"
        )
        await self._session.commit()

        logger.info(
            "Manual post created",
            post_id=saved.id,
            channel_id=channel.id,
            has_image=bool(image_url),
            has_video=bool(video_url),
            buttons=cleaned_buttons,
        )

        if publish_immediately:
            task = publish_post_task.delay(saved.id)
            await JobTracker(self._session).enqueue_publish(
                task.id, saved.id, channel.name
            )
            await self._session.commit()
            logger.info(
                "Manual publish queued",
                post_id=saved.id,
                celery_task_id=task.id,
            )

        return saved
