"""Tests for user-initiated Celery job cancellation."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.enums import JobStatus
from app.services.job_cancel import cancel_job_by_celery_id


@pytest.mark.asyncio
async def test_cancel_job_revokes_and_marks_cancelled() -> None:
    job = SimpleNamespace(
        id=42,
        celery_task_id="task-1",
        status=JobStatus.RUNNING.value,
        parent_celery_task_id=None,
    )
    child = SimpleNamespace(
        id=43,
        celery_task_id="task-child",
        status=JobStatus.QUEUED.value,
        parent_celery_task_id="task-1",
    )
    session = MagicMock()
    session.flush = AsyncMock()

    repo = MagicMock()
    repo.get_by_celery_id = AsyncMock(side_effect=[job, job])
    repo.list_children = AsyncMock(return_value=[child])

    tracker = MagicMock()
    tracker.mark_cancelled = AsyncMock()

    with (
        patch("app.services.job_cancel.BackgroundJobRepository", return_value=repo),
        patch("app.services.job_cancel.JobTracker", return_value=tracker),
        patch("app.services.job_cancel._revoke_celery") as revoke,
    ):
        result = await cancel_job_by_celery_id(session, "task-1")

    assert result is job
    assert revoke.call_count == 2
    revoke.assert_any_call("task-1")
    revoke.assert_any_call("task-child")
    assert tracker.mark_cancelled.await_count == 2


@pytest.mark.asyncio
async def test_cancel_job_rejects_terminal() -> None:
    job = SimpleNamespace(
        id=1,
        celery_task_id="done-1",
        status=JobStatus.SUCCESS.value,
    )
    session = MagicMock()
    repo = MagicMock()
    repo.get_by_celery_id = AsyncMock(return_value=job)

    with (
        patch("app.services.job_cancel.BackgroundJobRepository", return_value=repo),
        patch("app.services.job_cancel.JobTracker"),
        pytest.raises(ValueError),
    ):
        await cancel_job_by_celery_id(session, "done-1")
