"""Tests for animated cover publishing across platforms."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.publishers.max_publisher import MaxPublisher
from app.infrastructure.publishers.telegram_publisher import TelegramPublisher
from app.infrastructure.publishers.vk_publisher import VkPublisher
from app.services.publish_service import PublishService


@pytest.mark.asyncio
async def test_publish_service_loads_video_and_image() -> None:
    post = ProcessedPost(
        id=1,
        channel_id=1,
        rewritten_text="<p>text</p>",
        article_body="<p>body</p>",
        status="approved",
        generated_image_url="local://covers/x.png",
        generated_video_url="local://animations/x.mp4",
    )
    channel = Channel(
        id=1,
        name="Test",
        platform="max",
        platform_id="-1",
        topic="it",
        animate_postcards=True,
    )
    session = MagicMock()
    svc = PublishService(session)
    svc._processed.get_by_id = AsyncMock(return_value=post)
    svc._channels.get_by_id = AsyncMock(return_value=channel)
    svc._settings.get = AsyncMock(
        side_effect=lambda key, default="": {
            "posts_per_day": "10",
            "postcard_animation_enabled": "true",
        }.get(key, default)
    )
    svc._processed.count_published_today = AsyncMock(return_value=0)
    svc._processed.exists_by_hash = AsyncMock(return_value=False)
    svc._processed.update = AsyncMock()
    svc._logs.create = AsyncMock(return_value=SimpleNamespace(id=1))
    session.commit = AsyncMock()

    publisher = MagicMock()
    publisher.publish = AsyncMock(return_value="mid-1")

    with (
        patch("app.services.publish_service.get_publisher", return_value=publisher),
        patch.object(svc._images, "download_media_bytes", AsyncMock(return_value=b"mp4")),
        patch.object(svc._images, "download_and_resize", AsyncMock(return_value=b"jpg")),
    ):
        await svc.publish_post(1)

    publisher.publish.assert_awaited_once()
    args = publisher.publish.await_args
    assert args.args[2] == b"jpg"
    assert args.kwargs.get("video_bytes") == b"mp4"


@pytest.mark.asyncio
async def test_telegram_publish_uses_send_video() -> None:
    publisher = TelegramPublisher()
    channel = Channel(
        id=1,
        name="Открытки",
        platform="telegram",
        platform_id="-1001",
        topic="postcard",
        content_mode="article",
    )
    post = ProcessedPost(
        id=1,
        channel_id=1,
        rewritten_text="<b>Hi</b>",
        content_mode="article",
        article_title="Title",
        article_body="<p>Body</p>",
        status="approved",
    )
    with (
        patch("app.infrastructure.publishers.telegram_publisher.get_settings") as gs,
        patch("app.infrastructure.publishers.telegram_publisher.Bot") as bot_cls,
        patch.object(publisher, "_send_via_bot", AsyncMock(return_value="99")) as send_bot,
    ):
        gs.return_value.telegram_bot_token = "token"
        mock_bot = MagicMock()
        mock_bot.session.close = AsyncMock()
        bot_cls.return_value = mock_bot
        message_id = await publisher.publish(post, channel, b"img", video_bytes=b"mp4")
    assert message_id == "99"
    send_bot.assert_awaited_once()
    assert send_bot.await_args.args[4] == b"mp4"


@pytest.mark.asyncio
async def test_max_send_message_attaches_image_and_video() -> None:
    session = MagicMock()
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=ctx)
    ctx.__aexit__ = AsyncMock(return_value=False)
    ctx.json = AsyncMock(return_value={"message": {"message_id": "mid-1"}})
    ctx.status = 200
    session.post = MagicMock(return_value=ctx)

    with (
        patch.object(MaxPublisher, "_upload_image", AsyncMock(return_value="img-token")) as up_img,
        patch.object(MaxPublisher, "_upload_video", AsyncMock(return_value="video-token")) as up_vid,
        patch("app.infrastructure.publishers.max_publisher.asyncio.sleep", AsyncMock()),
    ):
        message_id = await MaxPublisher._send_message(
            session,
            "bot-token",
            123,
            "text",
            b"img",
            video_bytes=b"mp4",
        )
    assert message_id == "mid-1"
    up_img.assert_awaited_once()
    up_vid.assert_awaited_once()
    body = session.post.call_args.kwargs["json"]
    types = [a["type"] for a in body["attachments"]]
    assert types == ["image", "video"]


@pytest.mark.asyncio
async def test_max_send_message_retries_until_video_ready() -> None:
    session = MagicMock()
    not_ready = MagicMock()
    not_ready.__aenter__ = AsyncMock(return_value=not_ready)
    not_ready.__aexit__ = AsyncMock(return_value=False)
    not_ready.json = AsyncMock(
        return_value={
            "code": "attachment.not.ready",
            "message": "errors.process.attachment.video.not.processed",
        }
    )
    not_ready.status = 400

    ok = MagicMock()
    ok.__aenter__ = AsyncMock(return_value=ok)
    ok.__aexit__ = AsyncMock(return_value=False)
    ok.json = AsyncMock(return_value={"message": {"message_id": "mid-ok"}})
    ok.status = 200

    session.post = MagicMock(side_effect=[not_ready, not_ready, ok])
    sleep = AsyncMock()

    with (
        patch.object(MaxPublisher, "_upload_video", AsyncMock(return_value="video-token")),
        patch("app.infrastructure.publishers.max_publisher.asyncio.sleep", sleep),
    ):
        message_id = await MaxPublisher._send_message(
            session,
            "bot-token",
            123,
            "text",
            None,
            video_bytes=b"mp4",
        )

    assert message_id == "mid-ok"
    assert session.post.call_count == 3
    # initial delay + 2 retries
    assert sleep.await_count == 3


@pytest.mark.asyncio
async def test_vk_publish_prefers_video_attachment() -> None:
    publisher = VkPublisher()
    channel = Channel(id=1, name="VK", platform="vk", platform_id="-123", topic="it")
    post = ProcessedPost(id=1, channel_id=1, rewritten_text="<p>text</p>",
        article_body="<p>body</p>", status="approved")

    mock_resp = MagicMock()
    mock_resp.json = AsyncMock(return_value={"response": {"post_id": 42}})
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("app.infrastructure.publishers.vk_publisher.resolve_vk_token", AsyncMock(return_value="token")),
        patch("app.infrastructure.publishers.vk_publisher.resolve_vk_user_token", AsyncMock(return_value="user")),
        patch("app.infrastructure.publishers.vk_publisher.get_settings") as gs,
        patch("app.infrastructure.publishers.vk_publisher.aiohttp.ClientSession", return_value=mock_session),
        patch.object(publisher, "_upload_video", AsyncMock(return_value="video-1_2")) as up_video,
        patch.object(publisher, "_upload_photo", AsyncMock()) as up_photo,
    ):
        gs.return_value.vk_api_version = "5.199"
        post_id = await publisher.publish(post, channel, b"img", video_bytes=b"mp4")

    assert post_id == "42"
    up_video.assert_awaited_once()
    up_photo.assert_not_called()


@pytest.mark.asyncio
async def test_publish_service_skips_video_when_animation_disabled() -> None:
    post = ProcessedPost(
        id=1,
        channel_id=1,
        rewritten_text="<p>text</p>",
        article_body="<p>body</p>",
        status="approved",
        generated_image_url="local://covers/x.png",
        generated_video_url="local://animations/x.mp4",
    )
    channel = Channel(
        id=1,
        name="Test",
        platform="vk",
        platform_id="-1",
        topic="postcard",
        animate_postcards=True,
    )
    session = MagicMock()
    svc = PublishService(session)
    svc._processed.get_by_id = AsyncMock(return_value=post)
    svc._channels.get_by_id = AsyncMock(return_value=channel)
    svc._settings.get = AsyncMock(
        side_effect=lambda key, default="": {
            "posts_per_day": "10",
            "postcard_animation_enabled": "false",
        }.get(key, default)
    )
    svc._processed.count_published_today = AsyncMock(return_value=0)
    svc._processed.exists_by_hash = AsyncMock(return_value=False)
    svc._processed.update = AsyncMock()
    svc._logs.create = AsyncMock(return_value=SimpleNamespace(id=1))
    session.commit = AsyncMock()

    publisher = MagicMock()
    publisher.publish = AsyncMock(return_value="1")

    with (
        patch("app.services.publish_service.get_publisher", return_value=publisher),
        patch.object(
            svc._images, "download_media_bytes", AsyncMock(return_value=b"mp4")
        ) as dl_video,
        patch.object(
            svc._images, "download_and_resize", AsyncMock(return_value=b"jpg")
        ),
    ):
        await svc.publish_post(1)

    dl_video.assert_not_called()
    assert publisher.publish.await_args.kwargs.get("video_bytes") is None
