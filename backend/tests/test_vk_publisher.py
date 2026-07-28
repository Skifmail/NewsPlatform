"""Тесты сборки текста поста для VK."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.publishers.vk_publisher import (
    VkPublisher,
    _prepare_wall_photo_bytes,
    build_vk_message,
)


def _png_bytes() -> bytes:
    buf = BytesIO()
    Image.new("RGB", (64, 64), color=(10, 20, 30)).save(buf, format="PNG")
    return buf.getvalue()


def test_prepare_wall_photo_converts_png_to_jpeg() -> None:
    prepared = _prepare_wall_photo_bytes(_png_bytes())
    assert prepared is not None
    assert prepared.startswith(b"\xff\xd8")



def _post(article_body=None, rewritten_text=""):
    return SimpleNamespace(article_body=article_body, rewritten_text=rewritten_text)


def test_article_uses_full_body() -> None:
    """Для статьи берётся полный article_body, а не короткий анонс."""
    post = _post(
        article_body="<b>Заголовок</b>\n\nПолный текст статьи с <a href='u'>ссылкой</a>.",
        rewritten_text="короткий анонс",
    )
    msg = build_vk_message(post)
    assert "Полный текст статьи" in msg
    assert "короткий анонс" not in msg
    assert "<b>" not in msg and "<a" not in msg  # HTML вырезан


def test_news_uses_rewritten_text() -> None:
    post = _post(article_body=None, rewritten_text="<b>Новость</b> дня")
    msg = build_vk_message(post)
    assert "Новость дня" in msg
    assert "<b>" not in msg


def test_length_capped() -> None:
    post = _post(rewritten_text="a" * 20000)
    assert len(build_vk_message(post, limit=15000)) == 15000


def test_empty_post() -> None:
    assert build_vk_message(_post()) == ""


@pytest.mark.asyncio
async def test_vk_skips_doc_fallback_when_user_token_present() -> None:
    publisher = VkPublisher()
    channel = Channel(id=1, name="VK", platform="vk", platform_id="-123", topic="it")
    post = ProcessedPost(
        id=1,
        channel_id=1,
        rewritten_text="<p>text</p>",
        article_body="<p>body</p>",
        status="approved",
    )

    mock_resp = MagicMock()
    mock_resp.json = AsyncMock(return_value={"response": {"post_id": 42}})
    mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
    mock_resp.__aexit__ = AsyncMock(return_value=False)

    mock_session = MagicMock()
    mock_session.post = MagicMock(return_value=mock_resp)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.infrastructure.publishers.vk_publisher.resolve_vk_token",
            AsyncMock(return_value="group-token"),
        ),
        patch(
            "app.infrastructure.publishers.vk_publisher.resolve_vk_user_token",
            AsyncMock(return_value="user-token"),
        ),
        patch("app.infrastructure.publishers.vk_publisher.get_settings") as gs,
        patch(
            "app.infrastructure.publishers.vk_publisher.aiohttp.ClientSession",
            return_value=mock_session,
        ),
        patch.object(publisher, "_upload_photo", AsyncMock(return_value=None)) as up_photo,
        patch.object(publisher, "_upload_photo_as_doc", AsyncMock()) as up_doc,
    ):
        gs.return_value.vk_api_version = "5.199"
        post_id = await publisher.publish(post, channel, _png_bytes())

    assert post_id == "42"
    up_photo.assert_awaited_once()
    up_doc.assert_not_called()
