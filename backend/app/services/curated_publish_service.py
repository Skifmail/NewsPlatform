"""Автовыбор лучшей новости по теме → AI → публикация."""

from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.curated_pick import TOPIC_LABELS, CuratedPickRecord
from app.domain.enums import Topic
from app.domain.platform_settings import curated_scheduler_key
from app.repositories.channel_repository import ChannelRepository
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.repositories.raw_post_repository import RawPostRepository
from app.repositories.setting_repository import SettingRepository
from app.services.job_tracker import JobTracker
from app.services.platform_settings_service import PlatformSettingsService
from app.services.prompt_service import PromptService
from app.infrastructure.ai.topic_picker import TopicPicker
from app.tasks.ai_tasks import process_post_task

_CANDIDATE_LIMIT = 25


class CuratedPublishService:
    """Планировщик «лучшая новость темы → рерайт → каналы»."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._channels = ChannelRepository(session)
        self._raw = RawPostRepository(session)
        self._processed = ProcessedPostRepository(session)
        self._settings = SettingRepository(session)
        self._platform = PlatformSettingsService(session)
        self._prompts = PromptService(session)
        self._picker = TopicPicker()
        self._jobs = JobTracker(session)

    async def run_due_topics(self) -> dict[str, int | None]:
        """Запускает отбор и публикацию для тем, у которых наступил слот.

        Returns:
            dict[str, int | None]: topic → raw_post_id или None если пропуск.
        """
        platform = await self._platform.load()
        if not platform.schedule_curated_publish_enabled:
            return {}

        pick_prompt = await self._prompts.get("topic_selection.curated_pick")
        pick_system = await self._prompts.get("topic_selection.curated_pick_system")

        now = datetime.now(UTC)
        interval_minutes = max(1, platform.fetch_interval_minutes)
        result: dict[str, int | None] = {}
        for topic in Topic:
            raw_id = await self._try_topic(
                topic=topic.value,
                now=now,
                pick_prompt=pick_prompt,
                pick_system=pick_system,
                interval_minutes=interval_minutes,
            )
            result[topic.value] = raw_id
        return result

    async def _try_topic(
        self,
        *,
        topic: str,
        now: datetime,
        pick_prompt: str,
        pick_system: str,
        interval_minutes: int,
    ) -> int | None:
        """Пытается поставить в очередь лучший материал одной темы.

        Args:
            topic: it | auto | russia | sport.
            now: текущий момент UTC.
            pick_prompt: шаблон промпта выбора.
            pick_system: системный промпт выбора.
            interval_minutes: минимальный интервал между публикациями темы
                (совпадает с fetch_interval_minutes платформы).

        Returns:
            int | None: id raw_post или None.
        """
        channels = await self._channels.list_active_by_topic(topic)
        if not channels:
            return None

        interval = max(1, interval_minutes)
        last_key = curated_scheduler_key(topic)
        last_raw = (await self._settings.get(last_key, "")).strip()
        if last_raw:
            try:
                last_at = datetime.fromisoformat(last_raw)
                if now - last_at < timedelta(minutes=interval):
                    return None
            except ValueError:
                pass

        candidates = await self._raw.list_filtered(
            topic=Topic(topic),
            is_processed=False,
            limit=_CANDIDATE_LIMIT,
        )
        if not candidates:
            return None

        pick = await self._picker.pick_best(
            topic, candidates, pick_prompt, pick_system
        )
        if pick is None:
            return None

        topic_label = TOPIC_LABELS.get(topic, topic)
        job_label = f"Умная публикация · {topic_label}: #{pick.raw_post_id}"
        if pick.title:
            short_title = pick.title if len(pick.title) <= 72 else f"{pick.title[:69]}…"
            job_label = f"{job_label} — {short_title}"

        celery_result = process_post_task.delay(pick.raw_post_id, curated=True)
        await self._jobs.enqueue_process(
            celery_result.id,
            pick.raw_post_id,
            label=job_label,
            result_summary=f"Причина выбора: {pick.reason}",
        )
        await self._platform.record_curated_pick(
            CuratedPickRecord.create(
                topic=topic,
                topic_label=topic_label,
                pick=pick,
                candidates_count=len(candidates),
                picked_at=now,
            )
        )
        await self._platform.mark_curated_run(topic, now)
        await self._session.commit()

        logger.info(
            "Curated publish queued",
            topic=topic,
            raw_post_id=pick.raw_post_id,
            title=pick.title,
            reason=pick.reason,
            celery_task_id=celery_result.id,
            candidates=len(candidates),
        )
        return pick.raw_post_id
