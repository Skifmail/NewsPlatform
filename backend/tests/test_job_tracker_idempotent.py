"""Tests for idempotent JobTracker.enqueue_* under unique celery_task_id.

Callers: pytest. Covers race when API and worker both register the same task.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import IntegrityError

from app.infrastructure.models.background_job import BackgroundJob
from app.services.job_tracker import JobTracker


@pytest.mark.asyncio
async def test_enqueue_publish_returns_existing_on_duplicate() -> None:
    session = MagicMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)

    existing = BackgroundJob(
        id=9,
        celery_task_id="same-id",
        job_type="publish",
        status="queued",
        label="Публикация: X",
    )
    tracker = JobTracker(session)
    tracker._repo.get_by_celery_id = AsyncMock(side_effect=[None, existing])
    tracker._repo.create = AsyncMock(
        side_effect=IntegrityError("INSERT", {}, Exception("unique"))
    )
    tracker._notify = AsyncMock()

    result = await tracker.enqueue_publish("same-id", 1, "ПАРАГРАФ")
    assert result is existing
    tracker._notify.assert_awaited_once_with(existing)


@pytest.mark.asyncio
async def test_enqueue_publish_creates_when_missing() -> None:
    session = MagicMock()
    nested = MagicMock()
    nested.__aenter__ = AsyncMock(return_value=None)
    nested.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested = MagicMock(return_value=nested)

    created = BackgroundJob(
        id=1,
        celery_task_id="new-id",
        job_type="publish",
        status="queued",
        label="Публикация: X",
    )
    tracker = JobTracker(session)
    tracker._repo.get_by_celery_id = AsyncMock(return_value=None)
    tracker._repo.create = AsyncMock(return_value=created)
    tracker._notify = AsyncMock()

    result = await tracker.enqueue_publish("new-id", 1, "X")
    assert result is created
