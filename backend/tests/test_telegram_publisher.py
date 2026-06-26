"""Тесты TelegramPublisher: long-form и fallback на бота."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.publishers.telegram_publisher import TelegramPublisher
from app.infrastructure.publishers.telegram_user_publisher import TelethonNotReadyError


@pytest.fixture
def github_channel() -> Channel:
    return Channel(
        id=6,
        name="Github | Находки",
        platform="telegram",
        platform_id="-1004461561041",
        topic="it",
        content_mode="article",
    )


@pytest.fixture
def article_post() -> ProcessedPost:
    return ProcessedPost(
        id=1,
        channel_id=6,
        rewritten_text="<b>tool</b>\n\nКрючок",
        content_mode="article",
        article_title="Заголовок",
        article_body="<b>Раздел</b>\n\n" + ("текст " * 400),
        status="approved",
    )


@pytest.mark.asyncio
async def test_news_with_image_prefers_userbot() -> None:
    publisher = TelegramPublisher()
    channel = Channel(
        id=2,
        name="АВТОСФЕРА | Новости",
        platform="telegram",
        platform_id="-1004244141982",
        topic="auto",
        content_mode="news",
    )
    post = ProcessedPost(
        id=1,
        channel_id=2,
        rewritten_text="Новость " * 200,
        content_mode="news",
        status="approved",
    )
    with (
        patch.object(
            publisher._user_publisher,
            "publish",
            new_callable=AsyncMock,
            return_value="55",
        ) as user_publish,
        patch.object(
            publisher,
            "_send_via_bot",
            new_callable=AsyncMock,
        ) as bot_send,
        patch("app.infrastructure.publishers.telegram_publisher.get_settings") as gs,
        patch("app.infrastructure.publishers.telegram_publisher.Bot") as bot_cls,
    ):
        gs.return_value.telegram_bot_token = "token"
        mock_bot = MagicMock()
        mock_bot.session.close = AsyncMock()
        bot_cls.return_value = mock_bot
        message_id = await publisher.publish(post, channel, b"img")
    assert message_id == "55"
    user_publish.assert_awaited_once()
    bot_send.assert_not_called()


@pytest.mark.asyncio
async def test_long_form_article_uses_userbot_when_ready(
    github_channel: Channel,
    article_post: ProcessedPost,
) -> None:
    publisher = TelegramPublisher()
    with (
        patch.object(
            publisher._user_publisher,
            "publish",
            new_callable=AsyncMock,
            return_value="42",
        ) as user_publish,
        patch.object(
            publisher,
            "_send_via_bot",
            new_callable=AsyncMock,
        ) as bot_send,
        patch("app.infrastructure.publishers.telegram_publisher.get_settings") as gs,
        patch("app.infrastructure.publishers.telegram_publisher.Bot") as bot_cls,
    ):
        gs.return_value.telegram_bot_token = "token"
        mock_bot = MagicMock()
        mock_bot.session.close = AsyncMock()
        bot_cls.return_value = mock_bot
        message_id = await publisher._publish_long_form_article(
            article_post,
            github_channel,
            b"fake-image",
        )
    assert message_id == "42"
    user_publish.assert_awaited_once()
    bot_send.assert_not_awaited()


@pytest.mark.asyncio
async def test_long_form_falls_back_to_bot_when_telethon_not_ready(
    github_channel: Channel,
    article_post: ProcessedPost,
) -> None:
    publisher = TelegramPublisher()
    with (
        patch.object(
            publisher._user_publisher,
            "publish",
            new_callable=AsyncMock,
            side_effect=TelethonNotReadyError("no session"),
        ),
        patch.object(
            publisher,
            "_send_via_bot",
            new_callable=AsyncMock,
            return_value="99",
        ) as bot_send,
        patch("app.infrastructure.publishers.telegram_publisher.get_settings") as gs,
        patch("app.infrastructure.publishers.telegram_publisher.Bot") as bot_cls,
    ):
        gs.return_value.telegram_bot_token = "token"
        mock_bot = MagicMock()
        mock_bot.session.close = AsyncMock()
        bot_cls.return_value = mock_bot
        message_id = await publisher._publish_long_form_article(
            article_post,
            github_channel,
            b"fake-image",
        )
    assert message_id == "99"
    bot_send.assert_awaited_once()
