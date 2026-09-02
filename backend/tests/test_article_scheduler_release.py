"""Тест сброса слота планировщика после провала генерации."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.article_scheduler_recovery import release_article_scheduler_slot


@pytest.mark.asyncio
async def test_release_article_scheduler_slot_clears_setting() -> None:
    mock_repo = AsyncMock()
    mock_session = AsyncMock()
    mock_factory = AsyncMock()
    mock_factory.__aenter__.return_value = mock_session
    mock_factory.__aexit__.return_value = None

    with patch(
        "app.services.article_scheduler_recovery.async_session_factory",
        return_value=mock_factory,
    ), patch(
        "app.services.article_scheduler_recovery.SettingRepository",
        return_value=mock_repo,
    ):
        await release_article_scheduler_slot(7)

    mock_repo.set.assert_awaited_once_with("scheduler_last_article_7", "")
    mock_session.commit.assert_awaited_once()
