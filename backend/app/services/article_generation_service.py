"""Оркестрация генерации автономных статей."""

import re

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.article import (
    article_topic_history_key,
    parse_topic_history,
    serialize_research_sources,
    serialize_topic_history,
)
from app.domain.topic_dedup import is_topic_too_similar, merge_topic_lists
from app.domain.tool_category import is_ai_tool
from app.domain.enums import ContentMode, PostStatus
from app.infrastructure.ai.article_writer import ArticleWriter, WriterPrompts
from app.infrastructure.ai.devtools_teaser_formatter import (
    extract_devtools_hook,
    is_devtools_article_channel,
)
from app.infrastructure.ai.paragraph_teaser_formatter import is_paragraph_article_channel
from app.infrastructure.ai.postcard_teaser_formatter import is_postcard_article_channel
from app.infrastructure.ai.image_service import ImageGenPrompts, ImageService
from app.infrastructure.ai.topic_ideation import IdeationPrompts, TopicIdeationService
from app.infrastructure.parsers.github_repo_logo import parse_github_repo
from app.infrastructure.search.github_trending_client import (
    GitHubTrendingClient,
    TrendingRepo,
)
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.channel_repository import ChannelRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.setting_repository import SettingRepository
from app.services.job_tracker import report_job_stage
from app.services.media_asset_service import MediaAssetService
from app.services.pipeline_emitter import emit_internal, skip_step
from app.services.platform_settings_service import PlatformSettingsService
from app.services.postcard_theme_service import PostcardThemeService
from app.services.prompt_service import PromptService
from app.services.web_research_service import WebResearchService
from app.utils.telegram_channels import is_telegram_long_form_channel
from app.utils.text_format import long_form_body_limit

_MAX_DRAFT_DEDUP_ATTEMPTS = 3
_GITHUB_URL_RE = re.compile(r"https?://github\.com/[^\s\"'<>)]+", re.IGNORECASE)


class ArticleGenerationService:
    """Генерирует познавательную статью для article-канала."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._channels = ChannelRepository(session)
        self._processed = ProcessedPostRepository(session)
        self._settings = SettingRepository(session)
        self._prompts = PromptService(session)
        self._research = WebResearchService()
        self._trending = GitHubTrendingClient()

    async def _load_ideation_prompts(self) -> IdeationPrompts:
        """Загружает промпты идеации из БД (падает PromptNotFoundError)."""
        return IdeationPrompts(
            default_template=await self._prompts.get("ideation.default"),
            postcard_template=await self._prompts.get("ideation.postcard"),
            manual_topic_template=await self._prompts.get("ideation.manual_topic"),
            manual_postcard_template=await self._prompts.get(
                "ideation.manual_postcard"
            ),
            system_default=await self._prompts.get("ideation.system_default"),
            system_postcard=await self._prompts.get("ideation.system_postcard"),
            system_paragraph=await self._prompts.get("ideation.system_paragraph"),
            devtools_extra=await self._prompts.get("ideation.devtools_extra"),
            devtools_with_repos=await self._prompts.get(
                "ideation.devtools_with_repos"
            ),
            devtools_no_repos=await self._prompts.get("ideation.devtools_no_repos"),
            paragraph_extra=await self._prompts.get("ideation.paragraph_extra"),
        )

    async def _load_writer_prompts(self) -> WriterPrompts:
        """Загружает промпты написания статей из БД."""
        return WriterPrompts(
            default_template=await self._prompts.get("writing.default"),
            postcard_template=await self._prompts.get("writing.postcard"),
            system_default=await self._prompts.get("writing.system_default"),
            system_devtools=await self._prompts.get("writing.system_devtools"),
            system_paragraph=await self._prompts.get("writing.system_paragraph"),
            system_postcard=await self._prompts.get("writing.system_postcard"),
            devtools_instructions=await self._prompts.get(
                "writing.devtools_instructions"
            ),
            paragraph_instructions=await self._prompts.get(
                "writing.paragraph_instructions"
            ),
            image_hint_default=await self._prompts.get("image.writer_hint_default"),
            image_hint_postcard=await self._prompts.get("image.writer_hint_postcard"),
            image_hint_paragraph=await self._prompts.get(
                "image.writer_hint_paragraph"
            ),
        )

    async def _load_image_prompts(self) -> ImageGenPrompts:
        """Загружает негативы и шаблон обложки из БД."""
        return ImageGenPrompts(
            no_text_negative=await self._prompts.get("negative.qwen_no_text"),
            news_negative=await self._prompts.get("negative.qwen_news"),
            cover_template=await self._prompts.get("image.cover_prompt"),
            postcard_cover_template=await self._prompts.get(
                "image.cover_prompt_postcard"
            ),
            postcard_animation_template=await self._prompts.get(
                "image.postcard_animation"
            ),
        )

    async def generate_for_channel(
        self,
        channel_id: int,
        *,
        celery_task_id: str | None = None,
        topic: str | None = None,
    ) -> int:
        """Создаёт статью для канала.

        Args:
            channel_id: ID канала с content_mode=article.
            celery_task_id: ID Celery-задачи для поэтапных уведомлений UI.
            topic: ручная тема/повод; None — ИИ выбирает сам.

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

        platform_settings = await PlatformSettingsService(self._session).get_merged()
        ideation = TopicIdeationService(await self._load_ideation_prompts())
        writer = ArticleWriter(await self._load_writer_prompts())
        teaser_max = int(await self._settings.get("article_teaser_max_length", "900"))
        body_max = int(await self._settings.get("article_body_max_length", "12000"))
        telegram_max = int(await self._settings.get("article_telegram_max_length", "3800"))
        tavily_keys_raw = platform_settings.get("tavily_api_keys")
        tavily_active_key_id = platform_settings.get("tavily_active_key_id", "")
        tavily_auto_switch = (
            str(platform_settings.get("tavily_auto_switch", "true")).lower()
            in {"true", "1", "yes", "on"}
        )

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
        recent = await self._load_recent_topics(channel)
        settings_history = parse_topic_history(await self._settings.get(history_key, ""))

        recent_hooks: list[str] | None = None
        candidate_repos: list[str] | None = None
        if is_devtools_article_channel(channel.topic, channel.name):
            teasers = await self._processed.list_recent_article_teasers(channel_id, limit=12)
            recent_hooks = [
                hook
                for teaser in teasers
                if (hook := extract_devtools_hook(teaser))
            ][:8] or None
            # Правило «≤1 AI-инструмента из 3 подряд»: если хотя бы один из
            # последних 2 постов — AI/LLM, новый пост должен быть не-AI.
            last_titles = await self._processed.list_recent_article_titles(
                channel_id, limit=2
            )
            exclude_ai = any(is_ai_tool(title) for title in last_titles)
            candidate_repos = await self._load_trending_candidates(
                channel_id, exclude_ai=exclude_ai
            )

        draft = None
        plan = None
        sources = []
        research_context = ""
        manual_topic = (topic or "").strip() or None
        is_postcard = is_postcard_article_channel(channel.name, channel.topic or "")
        selected_postcard_theme = None
        postcard_theme_service: PostcardThemeService | None = None
        if is_postcard:
            postcard_theme_service = PostcardThemeService(self._session)
            if not manual_topic:
                selected_postcard_theme = await postcard_theme_service.pick_next(channel)
                manual_topic = selected_postcard_theme.name

        for draft_attempt in range(1, _MAX_DRAFT_DEDUP_ATTEMPTS + 1):
            await report_job_stage(
                celery_task_id, "Выбор темы и угла статьи…", 25
            )
            if manual_topic:
                plan = await ideation.plan_manual_topic(channel, manual_topic)
            else:
                plan = await ideation.plan_topic(
                    channel, recent, candidate_repos=candidate_repos
                )
            emit_internal(
                label="Тема и угол определены",
                detail=f"«{plan.topic}» — {plan.angle}",
                progress=30,
                metadata={"queries": plan.search_queries},
            )

            if is_postcard:
                research_context = ""
                sources = []
                skip_step(
                    label="Веб-поиск пропущен",
                    reason="Открытки не требуют внешних источников",
                    progress=42,
                    to_node="tavily",
                )
            else:
                await report_job_stage(
                    celery_task_id, "Поиск материалов в интернете…", 42
                )
                research_context, sources = await self._research.research(
                    plan.search_queries,
                    keys_raw=tavily_keys_raw,
                    active_key_id=tavily_active_key_id or None,
                    auto_switch=tavily_auto_switch,
                )

            await report_job_stage(
                celery_task_id, "Написание статьи через AI…", 62
            )
            draft = await writer.write(
                channel,
                topic=plan.topic,
                angle=plan.angle,
                research_context=research_context,
                body_max_length=body_max,
                teaser_max_length=teaser_max,
                recent_hooks=recent_hooks,
            )
            emit_internal(
                label="Черновик статьи готов",
                detail=f"«{draft.title}» — {len(draft.body_html)} симв. HTML",
                progress=75,
            )

            # Ручная тема и devtools/trending: дедуп заголовка не ретраим.
            if (
                manual_topic
                or candidate_repos
                or not is_topic_too_similar(draft.title, recent)
            ):
                break

            logger.warning(
                "Article title rejected as duplicate",
                channel_id=channel_id,
                title=draft.title,
                topic=plan.topic,
                attempt=draft_attempt,
            )
            recent = merge_topic_lists(
                [plan.topic, plan.angle, draft.title],
                recent,
                limit=50,
            )
            if draft_attempt >= _MAX_DRAFT_DEDUP_ATTEMPTS:
                msg = (
                    f"Не удалось сгенерировать уникальный заголовок "
                    f"(последний: {draft.title})"
                )
                raise RuntimeError(msg)

        await report_job_stage(
            celery_task_id, "Генерация обложки…", 80
        )
        images = ImageService.from_settings_dict(
            platform_settings, prompts=await self._load_image_prompts()
        )
        fallback_image = sources[0].url if sources else None
        image_url, image_source = await images.resolve_article_image(
            channel=channel,
            article_title=draft.title,
            topic=plan.topic,
            image_prompt=draft.image_prompt,
            fallback_url=fallback_image,
            repo_url=draft.repo_url,
            teaser=draft.teaser,
            greeting_text=draft.greeting_text,
        )

        video_url = None
        if image_url:
            await report_job_stage(
                celery_task_id, "Анимация обложки…", 88
            )
            video_url = await images.maybe_animate_postcard(
                channel=channel,
                image_url=image_url,
                article_title=draft.title,
            )
            if not video_url:
                skip_step(
                    label="Анимация обложки пропущена",
                    reason="Отключена для канала или недоступен OpenRouter",
                    progress=90,
                    to_node="openrouter",
                )
        elif not image_url:
            skip_step(
                label="Обложка не сгенерирована",
                reason="Нет изображения для публикации",
                progress=85,
                to_node="openai",
            )

        emit_internal(
            label="Медиа подготовлено",
            detail=(
                f"Изображение: {image_source or 'нет'}"
                + (f", видео: {video_url}" if video_url else "")
            ),
            progress=91,
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
            generated_video_url=video_url,
            image_source=image_source,
            ai_model=settings.deepseek_model,
            status=PostStatus.PENDING.value,
        )
        saved = await self._processed.create(processed)
        await MediaAssetService(self._session).register_from_post(
            saved, title=draft.title
        )
        emit_internal(
            label="Сохранено в очередь модерации",
            detail=f"processed_post #{saved.id}",
            progress=95,
            metadata={"processed_post_id": saved.id},
        )

        updated_history = merge_topic_lists(
            [plan.topic, draft.title],
            settings_history,
            recent,
            limit=50,
        )
        await self._persist_topic_history(channel, updated_history)
        if selected_postcard_theme and postcard_theme_service is not None:
            await postcard_theme_service.record_publication(
                channel.id, selected_postcard_theme
            )
        else:
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

    async def _load_trending_candidates(
        self, channel_id: int, *, limit: int = 25, exclude_ai: bool = False
    ) -> list[str] | None:
        """Готовит живой список трендовых репозиториев без уже опубликованных.

        Args:
            channel_id: ID devtools-канала.
            limit: максимум кандидатов для промпта идеации.
            exclude_ai: убрать AI/LLM-репозитории (правило «≤1 AI из 3 подряд»).

        Returns:
            list[str] | None: строки-описания репозиториев или None, если
                живой список получить не удалось (тогда идеация — «из памяти»).
        """
        trending = await self._trending.fetch_trending(limit=limit * 2)
        if not trending:
            return None

        posted = await self._posted_repo_full_names(channel_id)
        fresh: list[TrendingRepo] = [
            repo for repo in trending if repo.full_name.lower() not in posted
        ]
        if not fresh:
            logger.info(
                "All trending repos already posted, ideation falls back",
                channel_id=channel_id,
                trending=len(trending),
            )
            return None

        selected = fresh
        if exclude_ai:
            non_ai = [
                repo
                for repo in fresh
                if not is_ai_tool(f"{repo.full_name} {repo.description}")
            ]
            # Если после фильтра пусто — не ломаем генерацию, берём как есть.
            selected = non_ai or fresh

        logger.info(
            "Trending candidates prepared",
            channel_id=channel_id,
            total=len(trending),
            after_dedup=len(fresh),
            exclude_ai=exclude_ai,
            after_ai_filter=len(selected),
        )
        return [repo.as_candidate_line() for repo in selected[:limit]]

    async def _posted_repo_full_names(self, channel_id: int) -> set[str]:
        """Собирает owner/repo из недавних статей канала для дедупа.

        Args:
            channel_id: ID канала.

        Returns:
            set[str]: нормализованные (lowercase) full_name опубликованных репо.
        """
        bodies = await self._processed.list_recent_article_bodies(channel_id)
        posted: set[str] = set()
        for text in bodies:
            for match in _GITHUB_URL_RE.finditer(text):
                parsed = parse_github_repo(match.group(0))
                if parsed:
                    posted.add(f"{parsed[0]}/{parsed[1]}".lower())
        return posted

    async def _load_recent_topics(self, channel: Channel) -> list[str]:
        """Собирает историю тем с учётом связанных каналов (Параграф TG + MAX).

        Args:
            channel: канал публикации.

        Returns:
            list[str]: темы и заголовки от новых к старым.
        """
        channel_ids = await self._article_history_channel_ids(channel)
        db_titles = await self._processed.list_recent_article_titles_for_channels(
            channel_ids,
            limit=50,
            days=60,
        )
        settings_parts: list[str] = []
        for cid in channel_ids:
            raw = await self._settings.get(article_topic_history_key(cid), "")
            settings_parts.extend(parse_topic_history(raw))
        return merge_topic_lists(db_titles, settings_parts, limit=50)

    async def _article_history_channel_ids(self, channel: Channel) -> list[int]:
        """ID каналов, чья история статей учитывается при антиповторе.

        Args:
            channel: текущий канал.

        Returns:
            list[int]: один или несколько ID.
        """
        if is_paragraph_article_channel(channel.name):
            article_channels = await self._channels.list_active_article_channels()
            return [
                ch.id
                for ch in article_channels
                if is_paragraph_article_channel(ch.name)
            ] or [channel.id]
        return [channel.id]

    async def _persist_topic_history(
        self, channel: Channel, topics: list[str]
    ) -> None:
        """Сохраняет историю тем; для «Параграф» — во все связанные каналы.

        Args:
            channel: канал публикации.
            topics: темы от новых к старым.
        """
        serialized = serialize_topic_history(topics, limit=50)
        keys = [
            article_topic_history_key(cid)
            for cid in await self._article_history_channel_ids(channel)
        ]
        for key in dict.fromkeys(keys):
            await self._settings.set(key, serialized)
