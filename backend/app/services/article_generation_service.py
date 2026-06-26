"""Оркестрация генерации автономных статей."""

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.article import (
    article_topic_history_key,
    parse_topic_history,
    serialize_research_sources,
    serialize_topic_history,
)
from app.domain.topic_dedup import merge_topic_lists
from app.domain.enums import ContentMode, PostStatus
from app.infrastructure.ai.article_writer import ArticleWriter
from app.infrastructure.ai.devtools_teaser_formatter import (
    extract_devtools_hook,
    is_devtools_article_channel,
)
from app.infrastructure.ai.image_service import ImageService
from app.infrastructure.ai.topic_ideation import TopicIdeationService
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.channel_repository import ChannelRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.setting_repository import SettingRepository
from app.services.job_tracker import report_job_stage
from app.services.platform_settings_service import PlatformSettingsService
from app.services.web_research_service import WebResearchService
from app.utils.telegram_channels import is_telegram_long_form_channel
from app.utils.text_format import long_form_body_limit


class ArticleGenerationService:
    """Генерирует познавательную статью для article-канала."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._channels = ChannelRepository(session)
        self._processed = ProcessedPostRepository(session)
        self._settings = SettingRepository(session)
        self._ideation = TopicIdeationService()
        self._research = WebResearchService()
        self._writer = ArticleWriter()

    async def generate_for_channel(
        self, channel_id: int, *, celery_task_id: str | None = None
    ) -> int:
        """Создаёт статью для канала.

        Args:
            channel_id: ID канала с content_mode=article.
            celery_task_id: ID Celery-задачи для поэтапных уведомлений UI.

        Returns:
            int: ID созданного processed_post.

        Raises:
            ValueError: канал не найден или не в режиме статей.
            RuntimeError: ошибка генерации.
        """
        channel = await self._channels.get_by_id(channel_id)
        if not channel:
            msg = f"Channel {channel_id} not found"
            raise ValueError(msg)
        if channel.content_mode != ContentMode.ARTICLE.value:
            msg = f"Channel {channel_id} is not in article mode"
            raise ValueError(msg)

        await report_job_stage(
            celery_task_id, "Загрузка настроек канала…", 12
        )

        ideation_prompt = await self._settings.get("article_ideation_prompt", "")
        writing_prompt = await self._settings.get("article_writing_prompt", "")
        teaser_max = int(await self._settings.get("article_teaser_max_length", "900"))
        body_max = int(await self._settings.get("article_body_max_length", "12000"))
        telegram_max = int(await self._settings.get("article_telegram_max_length", "3800"))

        if is_telegram_long_form_channel(channel):
            # Тело должно поместиться вместе с анонсом и футером в одно сообщение,
            # иначе обрезается блок «Источники» и кросс-промо ссылка.
            fit_budget = long_form_body_limit(
                platform=channel.platform, teaser_max_length=teaser_max
            )
            body_max = min(body_max, telegram_max, fit_budget)
            logger.info(
                "Long-form article limits",
                channel_id=channel_id,
                platform=channel.platform,
                body_max=body_max,
                fit_budget=fit_budget,
            )

        history_key = article_topic_history_key(channel_id)
        settings_history = parse_topic_history(await self._settings.get(history_key, ""))
        db_titles = await self._processed.list_recent_article_titles(channel_id, limit=30)
        recent = merge_topic_lists(db_titles, settings_history, limit=40)

        recent_hooks: list[str] | None = None
        if is_devtools_article_channel(channel.topic, channel.name):
            teasers = await self._processed.list_recent_article_teasers(channel_id, limit=12)
            recent_hooks = [
                hook
                for teaser in teasers
                if (hook := extract_devtools_hook(teaser))
            ][:8] or None

        await report_job_stage(
            celery_task_id, "Выбор темы и угла статьи…", 25
        )
        plan = await self._ideation.plan_topic(channel, recent, ideation_prompt)

        await report_job_stage(
            celery_task_id, "Поиск материалов в интернете…", 42
        )
        research_context, sources = await self._research.research(plan.search_queries)

        await report_job_stage(
            celery_task_id, "Написание статьи через AI…", 62
        )
        draft = await self._writer.write(
            channel,
            topic=plan.topic,
            angle=plan.angle,
            research_context=research_context,
            prompt_template=writing_prompt,
            body_max_length=body_max,
            teaser_max_length=teaser_max,
            recent_hooks=recent_hooks,
        )

        await report_job_stage(
            celery_task_id, "Генерация обложки…", 80
        )
        platform_settings = await PlatformSettingsService(self._session).get_merged()
        images = ImageService.from_settings_dict(platform_settings)
        fallback_image = sources[0].url if sources else None
        image_url, image_source = await images.resolve_article_image(
            channel=channel,
            article_title=draft.title,
            topic=plan.topic,
            image_prompt=draft.image_prompt,
            fallback_url=fallback_image,
            repo_url=draft.repo_url,
        )

        await report_job_stage(
            celery_task_id, "Сохранение в очередь модерации…", 92
        )
        settings = get_settings()
        processed = ProcessedPost(
            raw_post_id=None,
            channel_id=channel.id,
            rewritten_text=draft.teaser,
            content_mode=ContentMode.ARTICLE.value,
            article_title=draft.title,
            article_body=draft.body_html,
            research_sources=serialize_research_sources(sources),
            generated_image_url=image_url,
            image_source=image_source,
            ai_model=settings.deepseek_model,
            status=PostStatus.PENDING.value,
        )
        saved = await self._processed.create(processed)

        updated_history = merge_topic_lists(
            [plan.topic, draft.title],
            settings_history,
            limit=40,
        )
        await self._settings.set(history_key, serialize_topic_history(updated_history))
        await self._session.commit()

        auto_approve = (
            await self._settings.get("auto_approve", "false")
        ).lower() == "true"
        if auto_approve:
            saved.status = PostStatus.APPROVED.value
            await self._processed.update(saved)
            await self._session.commit()
            from app.tasks.publish_tasks import publish_post_task

            publish_post_task.delay(saved.id)

        logger.info(
            "Article generated",
            channel_id=channel_id,
            processed_post_id=saved.id,
            topic=plan.topic,
            sources=len(sources),
        )
        return saved.id
