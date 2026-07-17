"""Тесты CuratedPublishService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.curated_pick import TopicPickResult
from app.domain.platform_settings import PlatformSettings
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.raw_post import RawPost
from app.services.curated_publish_service import CuratedPublishService
from app.services.scheduling_service import SchedulingService


def _make_channel(
    *,
    topic: str = "russia",
    publish_interval_minutes: int = 60,
) -> Channel:
    """Собирает тестовый канал с широким окном публикации."""
    channel = Channel(
        name="Тест",
        platform="telegram",
        platform_id="1",
        topic=topic,
        publish_interval_minutes=publish_interval_minutes,
        publish_window_start="00:00",
        publish_window_end="23:59",
    )
    channel.id = 1
    return channel


def _make_raw_post(post_id: int = 42) -> RawPost:
    """Собирает тестовый сырой материал."""
    post = RawPost(
        source_id=1,
        external_id=f"ext-{post_id}",
        title="Заголовок",
        content="Текст",
        topic="russia",
        content_hash=f"hash-{post_id}",
    )
    post.id = post_id
    return post


def _platform_settings(**overrides: str) -> PlatformSettings:
    """Собирает снимок настроек с дефолтами для curated-тестов."""
    merged = {
        "schedule_curated_publish_enabled": "true",
        "fetch_interval_minutes": "30",
        **overrides,
    }
    return PlatformSettings.from_merged(merged)


@pytest.fixture
def service() -> CuratedPublishService:
    """Сервис с подменёнными зависимостями."""
    session = AsyncMock()
    curated = CuratedPublishService(session)
    curated._channels = AsyncMock()
    curated._raw = AsyncMock()
    curated._settings = AsyncMock()
    curated._platform = AsyncMock()
    curated._scheduling = SchedulingService(session)
    curated._picker = AsyncMock()
    curated._jobs = AsyncMock()
    return curated


@pytest.mark.asyncio
async def test_skips_topic_when_fetch_interval_not_elapsed(
    service: CuratedPublishService,
) -> None:
    """Пропускает тему, если с прошлого curated-запуска прошло меньше fetch_interval."""
    now = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
    service._channels.list_active_by_topic.return_value = [_make_channel()]
    service._settings.get.return_value = (now - timedelta(minutes=10)).isoformat()

    result = await service._try_topic(
        topic="russia",
        now=now,
        pick_prompt="prompt",
        interval_minutes=30,
    )

    assert result is None
    service._raw.list_filtered.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.curated_publish_service.process_post_task")
async def test_queues_pick_when_fetch_interval_elapsed(
    mock_process_task: MagicMock,
    service: CuratedPublishService,
) -> None:
    """Ставит рерайт в очередь, когда интервал парсинга выдержан."""
    now = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
    raw_post = _make_raw_post()
    pick = TopicPickResult(
        raw_post_id=raw_post.id,
        reason="Актуально",
        title="Заголовок",
        source_name="Источник",
    )
    mock_process_task.delay.return_value = MagicMock(id="celery-1")

    service._channels.list_active_by_topic.return_value = [_make_channel()]
    service._settings.get.return_value = (now - timedelta(minutes=35)).isoformat()
    service._raw.list_filtered.return_value = [raw_post]
    service._picker.pick_best.return_value = pick

    result = await service._try_topic(
        topic="russia",
        now=now,
        pick_prompt="prompt",
        interval_minutes=30,
    )

    assert result == raw_post.id
    mock_process_task.delay.assert_called_once_with(raw_post.id, curated=True)


@pytest.mark.asyncio
@patch("app.services.curated_publish_service.process_post_task")
async def test_ignores_posts_per_day_and_channel_interval(
    mock_process_task: MagicMock,
    service: CuratedPublishService,
) -> None:
    """Не блокирует curated из-за posts_per_day и не использует interval канала."""
    now = datetime(2026, 7, 17, 10, 0, tzinfo=UTC)
    raw_post = _make_raw_post()
    pick = TopicPickResult(
        raw_post_id=raw_post.id,
        reason="Важно",
        title="Заголовок",
        source_name="Источник",
    )
    mock_process_task.delay.return_value = MagicMock(id="celery-2")

    # Интервал канала 60 мин, но fetch_interval = 30 — прошло 31 мин с last run.
    service._channels.list_active_by_topic.return_value = [
        _make_channel(publish_interval_minutes=60)
    ]
    service._settings.get.return_value = (now - timedelta(minutes=31)).isoformat()
    service._raw.list_filtered.return_value = [raw_post]
    service._picker.pick_best.return_value = pick

    result = await service._try_topic(
        topic="russia",
        now=now,
        pick_prompt="prompt",
        interval_minutes=30,
    )

    assert result == raw_post.id


@pytest.mark.asyncio
async def test_skips_topic_outside_publish_window(
    service: CuratedPublishService,
) -> None:
    """Не публикует ночью, если окно канала уже закрыто."""
    now = datetime(2026, 7, 17, 3, 0, tzinfo=UTC)
    night_channel = _make_channel()
    night_channel.publish_window_start = "08:00"
    night_channel.publish_window_end = "22:00"
    service._channels.list_active_by_topic.return_value = [night_channel]

    result = await service._try_topic(
        topic="russia",
        now=now,
        pick_prompt="prompt",
        interval_minutes=30,
    )

    assert result is None
    service._settings.get.assert_not_awaited()


@pytest.mark.asyncio
@patch("app.services.curated_publish_service.process_post_task")
async def test_run_due_topics_uses_fetch_interval_from_platform(
    mock_process_task: MagicMock,
    service: CuratedPublishService,
) -> None:
    """run_due_topics передаёт fetch_interval_minutes платформы в отбор по темам."""
    now = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    service._platform.load.return_value = _platform_settings(
        fetch_interval_minutes="45",
    )
    service._settings.get.return_value = ""

    with patch.object(
        service,
        "_try_topic",
        new_callable=AsyncMock,
        return_value=None,
    ) as mock_try:
        with patch(
            "app.services.curated_publish_service.datetime",
        ) as mock_datetime:
            mock_datetime.now.return_value = now
            mock_datetime.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
            await service.run_due_topics()

    assert mock_try.await_count == 4
    first_call = mock_try.await_args_list[0].kwargs
    assert first_call["interval_minutes"] == 45
