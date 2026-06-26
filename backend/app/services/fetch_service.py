"""Сервис сбора контента из источников."""

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.fetch_result import FetchResult
from app.utils.fetch_window import fetch_cutoff_utc, is_within_fetch_window
from app.infrastructure.models.raw_post import RawPost
from app.infrastructure.parsers.parser_factory import get_parser
from app.repositories.raw_post_repository import RawPostRepository
from app.repositories.source_repository import SourceRepository
from app.services.job_tracker import report_job_stage
from app.services.platform_settings_service import PlatformSettingsService
from app.utils.hash_utils import content_hash


class FetchService:
    """Оркестрация парсинга и сохранения raw_posts.

    Отбор на этапе парсинга: дубликаты по ``(source_id, external_id)`` и свежесть
    (по умолчанию только вчера и сегодня UTC по ``published_at``).
    Промпт ``classification_prompt`` применяется позже, на этапе AI.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._sources = SourceRepository(session)
        self._raw_posts = RawPostRepository(session)

    async def fetch_source(
        self, source_id: int, *, celery_task_id: str | None = None
    ) -> FetchResult:
        """Парсит источник и сохраняет новые посты.

        Args:
            source_id: ID источника.
            celery_task_id: ID Celery-задачи для поэтапных уведомлений UI.

        Returns:
            FetchResult: статистика и ID созданных raw_posts.
        """
        await report_job_stage(celery_task_id, "Загрузка источника…", 18)
        source = await self._sources.get_by_id(source_id)
        if not source or not source.is_active:
            return FetchResult(created_ids=[])

        try:
            await report_job_stage(
                celery_task_id,
                f"Парсинг материалов: {source.name}…",
                45,
            )
            parser = get_parser(source)
            items = await parser.fetch_new(source)
        except Exception as exc:
            logger.exception(
                "Parser failed",
                source_id=source_id,
                source_name=source.name,
                error=str(exc),
            )
            return FetchResult(created_ids=[], fetch_error=str(exc))

        platform = await PlatformSettingsService(self._session).load()
        env_days = get_settings().fetch_max_age_days
        max_age_days = platform.fetch_max_age_days or env_days
        cutoff = fetch_cutoff_utc(max_age_days)
        created_ids: list[int] = []
        skipped = 0
        skipped_old = 0

        await report_job_stage(
            celery_task_id,
            "Фильтрация дубликатов и сохранение…",
            78,
        )

        for item in items:
            if not is_within_fetch_window(item.published_at, max_age_days):
                skipped_old += 1
                continue
            if await self._raw_posts.exists(source_id, item.external_id):
                skipped += 1
                continue

            post = RawPost(
                source_id=source_id,
                external_id=item.external_id,
                title=item.title,
                content=item.content,
                url=item.url,
                image_url=item.image_url,
                topic=item.topic,
                content_hash=content_hash(item.content),
                published_at=item.published_at,
                is_processed=False,
            )
            saved = await self._raw_posts.create(post)
            created_ids.append(saved.id)
            logger.info("Raw post saved", raw_post_id=saved.id, source_id=source_id)

        await self._sources.mark_fetched(source_id)
        await self._session.commit()

        logger.info(
            "Fetch completed",
            source_id=source_id,
            source_name=source.name,
            feed_items=len(items),
            skipped_duplicates=skipped,
            skipped_too_old=skipped_old,
            published_after=cutoff.isoformat(),
            created=len(created_ids),
        )
        return FetchResult(
            created_ids=created_ids,
            feed_items=len(items),
            skipped_duplicates=skipped,
            skipped_too_old=skipped_old,
        )
