"""Tests for manual publish service and dual MAX media attachments.

Callers: pytest suite. Covers ManualPublishService and MaxPublisher dual media.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.domain.enums import ImageSource
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.publishers.max_publisher import MaxPublisher
from app.services.manual_publish_service import ManualPublishService
from app.services.publish_service import PublishService


@pytest.mark.asyncio
async def test_manual_publish_creates_approved_post_with_buttons() -> None:
    channel = Channel(
        id=7,
        name="ПАРАГРАФ",
        platform="max",
        platform_id="-100",
        topic="it",
        content_mode="article",
    )
    session = MagicMock()
    session.commit = AsyncMock()
    svc = ManualPublishService(session)
    svc._channels.get_by_id = AsyncMock(return_value=channel)

    saved = ProcessedPost(
        id=42,
        channel_id=7,
        rewritten_text="<p>Hello</p>",
        status="approved",
    )
    svc._processed.create = AsyncMock(return_value=saved)

    with (
        patch(
            "app.services.manual_publish_service.MediaAssetService"
        ) as media_cls,
        patch(
            "app.services.manual_publish_service.publish_post_task"
        ) as task,
        patch(
            "app.services.manual_publish_service.JobTracker"
        ) as tracker_cls,
    ):
        media_cls.return_value.register_from_post = AsyncMock(return_value=[])
        task.delay.return_value = SimpleNamespace(id="celery-1")
        tracker_cls.return_value.enqueue_publish = AsyncMock()

        result = await svc.create_and_publish(
            channel_id=7,
            text="<b>Заголовок</b>\n\nТекст поста вручную.",
            button_options=["Да", "Нет"],
            image_url="local://manual/covers/a.jpg",
            video_url="local://manual/videos/b.mp4",
            publish_immediately=True,
        )

    assert result.id == 42
    created = svc._processed.create.await_args.args[0]
    assert created.status == "approved"
    assert created.image_source == ImageSource.MANUAL.value
    assert created.ai_model == "manual"
    assert created.generated_image_url == "local://manual/covers/a.jpg"
    assert created.generated_video_url == "local://manual/videos/b.mp4"
    assert created.article_body == created.rewritten_text
    assert '"button_options"' in (created.article_meta or "")
    assert "Да" in (created.article_meta or "")
    task.delay.assert_called_once_with(42)


@pytest.mark.asyncio
async def test_manual_publish_requires_two_buttons() -> None:
    channel = Channel(
        id=1,
        name="Открытки",
        platform="max",
        platform_id="-1",
        topic="postcard",
        content_mode="article",
    )
    session = MagicMock()
    svc = ManualPublishService(session)
    svc._channels.get_by_id = AsyncMock(return_value=channel)

    with pytest.raises(ValueError, match="callback"):
        await svc.create_and_publish(
            channel_id=1,
            text="Текст",
            button_options=["Только одна"],
            publish_immediately=False,
        )


@pytest.mark.asyncio
async def test_publish_service_loads_manual_video_without_animation_flag() -> None:
    post = ProcessedPost(
        id=1,
        channel_id=1,
        rewritten_text="<p>manual</p>",
        article_body="<p>manual</p>",
        status="approved",
        generated_image_url="local://manual/covers/x.png",
        generated_video_url="local://manual/videos/x.mp4",
        image_source=ImageSource.MANUAL.value,
        ai_model="manual",
    )
    channel = Channel(
        id=1,
        name="ПАРАГРАФ",
        platform="max",
        platform_id="-1",
        topic="it",
        animate_postcards=False,
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
    publisher.publish = AsyncMock(return_value="mid-1")

    with (
        patch("app.services.publish_service.get_publisher", return_value=publisher),
        patch.object(svc._images, "download_media_bytes", AsyncMock(return_value=b"mp4")),
        patch.object(svc._images, "download_and_resize", AsyncMock(return_value=b"jpg")),
    ):
        await svc.publish_post(1)

    assert publisher.publish.await_args.kwargs.get("video_bytes") == b"mp4"
    assert publisher.publish.await_args.args[2] == b"jpg"


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
