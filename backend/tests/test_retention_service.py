"""Тесты RetentionService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.retention_service import RetentionService


@pytest.mark.asyncio
async def test_cleanup_expired_deletes_unprocessed_and_expired_raw_posts() -> None:
    """Сначала удаляются необработанные материалы, затем общая очистка."""
    session = AsyncMock()
    session.execute = AsyncMock(
        side_effect=[
            MagicMock(rowcount=120),
            MagicMock(rowcount=5),
            MagicMock(rowcount=10),
            MagicMock(rowcount=40),
        ]
    )

    service = RetentionService(
        session,
        retention_days=30,
        raw_posts_retention_days=3,
    )
    stats = await service.cleanup_expired()

    assert stats.raw_posts_unprocessed == 120
    assert stats.publish_logs == 5
    assert stats.background_jobs == 10
    assert stats.raw_posts == 40
    assert session.execute.await_count == 4
    session.commit.assert_awaited_once()
