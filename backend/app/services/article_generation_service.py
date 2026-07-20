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
from app.domain.enums import ContentMode, PostStatus
from app.infrastructure.ai.article_writer import ArticleWriter
from app.infrastructure.ai.devtools_teaser_formatter import (
    extract_devtools_hook,
    is_devtools_article_channel,
)
from app.infrastructure.ai.paragraph_teaser_formatter import is_paragraph_article_channel
from app.infrastructure.ai.image_service import ImageService
from app.infrastructure.ai.topic_ideation import TopicIdeationService
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
from app.services.platform_settings_service import PlatformSettingsService
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
        self._ideation = TopicIdeationService()
        self._research = WebResearchService()
        self._writer = ArticleWriter()
        self._trending = GitHubTrendingClient()

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

        platform_settings = await PlatformSettingsService(self._session).get_merged()
        ideation_prompt = await self._settings.get("article_ideation_prompt", "")
        writing_prompt = await self._settings.get("article_writing_prompt", "")
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
            candidate_repos = await self._load_trending_candidates(channel_id)

        draft = None
        plan = None
        sources = []
        research_context = ""

        for draft_attempt in range(1, _MAX_DRAFT_DEDUP_ATTEMPTS + 1):
            await report_job_stage(
                celery_task_id, "Выбор темы и угла статьи…", 25
            )
            plan = await self._ideation.plan_topic(
                channel, recent, ideation_prompt, candidate_repos=candidate_repos
            )

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

            if not is_topic_too_similar(draft.title, recent):
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
            recent,
            limit=50,
        )
        await self._persist_topic_history(channel, updated_history)
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
        self, channel_id: int, *, limit: int = 25
    ) -> list[str] | None:
        """Готовит живой список трендовых репозиториев без уже опубликованных.

        Args:
            channel_id: ID devtools-канала.
            limit: максимум кандидатов для промпта идеации.

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

        logger.info(
            "Trending candidates prepared",
            channel_id=channel_id,
            total=len(trending),
            after_dedup=len(fresh),
        )
        return [repo.as_candidate_line() for repo in fresh[:limit]]

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
