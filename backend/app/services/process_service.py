"""Сервис AI-обработки сырых постов."""

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.enums import ImageSource, PostStatus
from app.domain.process_result import ProcessResult
from app.infrastructure.ai.classifier import TopicClassifier
from app.infrastructure.ai.image_service import ImageGenPrompts, ImageService
from app.infrastructure.ai.rewriter import ContentRewriter
from app.services.activity_notifier import notify_simple
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.notifications.alert_bot import send_alert
from app.repositories.channel_repository import ChannelRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.raw_post_repository import RawPostRepository
from app.repositories.setting_repository import SettingRepository
from app.services.job_tracker import report_job_stage
from app.services.platform_settings_service import PlatformSettingsService
from app.services.prompt_service import PromptService

from app.domain.topics import TOPIC_LABELS as _TOPIC_LABELS


class ProcessService:
    """Создаёт processed_posts для каждого канала темы."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._raw_posts = RawPostRepository(session)
        self._channels = ChannelRepository(session)
        self._processed = ProcessedPostRepository(session)
        self._settings = SettingRepository(session)
        self._prompts = PromptService(session)
        self._classifier = TopicClassifier()

    async def process_raw_post(
        self,
        raw_post_id: int,
        *,
        curated: bool = False,
        celery_task_id: str | None = None,
    ) -> ProcessResult:
        """Обрабатывает сырой пост через DeepSeek.

        Args:
            raw_post_id: ID raw_post.
            curated: True — автопубликация после рерайта (режим «лучшая новость»).
            celery_task_id: ID Celery-задачи для поэтапных уведомлений UI.

        Returns:
            ProcessResult: ID созданных processed_posts и пояснение.
        """
        await report_job_stage(celery_task_id, "Загрузка сырого поста…", 15)
        raw_post = await self._raw_posts.get_by_id(raw_post_id)
        if not raw_post:
            return ProcessResult([], "—", "Сырой пост не найден")

        if raw_post.is_processed:
            children = await self._raw_posts.count_processed_children(raw_post_id)
            if children > 0:
                return ProcessResult([], raw_post.topic, "Пост уже в очереди или опубликован")

        source_topic = raw_post.topic
        classification_prompt = await self._prompts.get("classification.user")
        classification_system = await self._prompts.get("classification.system")
        if classification_prompt.strip():
            await report_job_stage(
                celery_task_id, "Классификация темы через AI…", 28
            )
            detected_topic = await self._classifier.classify(
                raw_post.content,
                classification_prompt,
                classification_system,
                fallback_topic=source_topic,
            )
            raw_post.topic = detected_topic
            await self._session.flush()

        await report_job_stage(celery_task_id, "Подбор каналов публикации…", 38)
        channels = await self._channels.list_active_by_topic(raw_post.topic)
        if not channels and raw_post.topic != source_topic:
            fallback_channels = await self._channels.list_active_by_topic(source_topic)
            if fallback_channels:
                logger.info(
                    "No channels for classified topic, using source topic",
                    classified=raw_post.topic,
                    source_topic=source_topic,
                    raw_post_id=raw_post_id,
                )
                raw_post.topic = source_topic
                channels = fallback_channels
                await self._session.flush()

        if not channels:
            label = _TOPIC_LABELS.get(raw_post.topic, raw_post.topic)
            return ProcessResult(
                [],
                raw_post.topic,
                f"Нет активных каналов с темой «{label}». "
                "Добавьте канал в разделе «Каналы» или смените тему канала.",
            )

        settings = get_settings()
        platform_settings = await PlatformSettingsService(self._session).get_merged()
        image_prompts = ImageGenPrompts(
            no_text_negative=await self._prompts.get("negative.qwen_no_text"),
            news_negative=await self._prompts.get("negative.qwen_news"),
            cover_template=await self._prompts.get("image.cover_prompt"),
            postcard_cover_template=await self._prompts.get(
                "image.cover_prompt_postcard"
            ),
        )
        images = ImageService.from_settings_dict(
            platform_settings, prompts=image_prompts
        )
        rewriter = ContentRewriter(
            default_template=await self._prompts.get("rewrite.default"),
            system_prompt=await self._prompts.get("rewrite.system"),
            retry_suffix=await self._prompts.get("rewrite.strict_retry_suffix"),
        )
        created_ids: list[int] = []

        for channel in channels:
            try:
                await report_job_stage(
                    celery_task_id,
                    f"Рерайт текста для «{channel.name}»…",
                    55,
                )
                rewritten = await rewriter.rewrite(raw_post, channel)
                await report_job_stage(
                    celery_task_id,
                    f"Подбор изображения для «{channel.name}»…",
                    72,
                )
                image_url, image_source = await images.resolve_image(
                    raw_post,
                    channel,
                    generate_if_missing=ImageService.ai_generation_available(),
                )
                processed = ProcessedPost(
                    raw_post_id=raw_post_id,
                    channel_id=channel.id,
                    rewritten_text=rewritten,
                    generated_image_url=image_url,
                    image_source=image_source,
                    ai_model=settings.deepseek_model,
                    status=PostStatus.PENDING.value,
                )
                saved = await self._processed.create(processed)
                created_ids.append(saved.id)

                topic_label = _TOPIC_LABELS.get(channel.topic, channel.topic)
                await notify_simple(
                    f"post-{saved.id}",
                    kind="post",
                    phase="done",
                    title="Новый пост в очереди модерации",
                    detail=f"{channel.name} · {topic_label}",
                    progress=100,
                    raw_post_id=raw_post_id,
                )
            except Exception as exc:
                logger.error(
                    "Process failed for channel: {error}",
                    channel_id=channel.id,
                    raw_post_id=raw_post_id,
                    error=str(exc),
                )

        if not created_ids:
            await self._session.commit()
            return ProcessResult(
                [],
                raw_post.topic,
                "Рерайт не удался: проверьте логи celery_worker и DEEPSEEK_API_KEY",
            )

        await self._raw_posts.mark_processed(raw_post_id)
        await self._session.commit()

        await send_alert(
            f"Новые посты в очереди: {len(created_ids)} шт. (raw_post #{raw_post_id})"
        )

        auto_approve = (
            await self._settings.get("auto_approve", "false")
        ).lower() == "true"
        if auto_approve or curated:
            for pid in created_ids:
                post = await self._processed.get_by_id(pid)
                if post:
                    post.status = PostStatus.APPROVED.value
                    await self._processed.update(post)
            await self._session.commit()
            # Публикация по расписанию канала (publish_times, МСК): FIFO из
            # очереди APPROVED в слот планировщика. Умная публикация (curated)
            # обходит расписание — оно уже соблюдено при отборе темы.
            if curated:
                from app.tasks.publish_tasks import publish_post_task
                for pid in created_ids:
                    publish_post_task.delay(pid, bypass_daily_limit=True)

        return ProcessResult(created_ids, raw_post.topic)
