"""Tests for postcard animation via OpenRouter."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.infrastructure.ai.image_service import ImageGenPrompts, ImageService
from app.infrastructure.ai.openrouter_video_client import OpenRouterVideoClient


def _postcard_channel(*, animate: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=7,
        name="Открытки",
        topic="postcard",
        animate_postcards=animate,
        image_prompt_guidelines="Scene: {scene}",
    )


def _prompts() -> ImageGenPrompts:
    return ImageGenPrompts(
        no_text_negative="text",
        news_negative="portrait",
        cover_template="Cover {title}",
        postcard_cover_template="Сделай открытку с {title}",
        postcard_animation_template="Анимируй «{title}», текст неподвижен",
    )


@pytest.mark.asyncio
async def test_maybe_animate_skipped_when_channel_disabled() -> None:
    svc = ImageService(
        prompts=_prompts(),
        openrouter_api_key="or-key",
        postcard_animation_enabled=True,
    )
    result = await svc.maybe_animate_postcard(
        channel=_postcard_channel(animate=False),
        image_url="local://covers/x.png",
        article_title="День ВМФ",
    )
    assert result is None


@pytest.mark.asyncio
async def test_maybe_animate_skipped_when_globally_disabled() -> None:
    svc = ImageService(
        prompts=_prompts(),
        openrouter_api_key="or-key",
        postcard_animation_enabled=False,
    )
    result = await svc.maybe_animate_postcard(
        channel=_postcard_channel(animate=True),
        image_url="local://covers/x.png",
        article_title="День ВМФ",
    )
    assert result is None


@pytest.mark.asyncio
async def test_maybe_animate_success_saves_gif() -> None:
    """GIF conversion is deferred; animation is stored as MP4 for MAX/VK."""
    svc = ImageService(
        prompts=_prompts(),
        openrouter_api_key="or-key",
        postcard_animation_enabled=True,
        postcard_animation_as_gif=True,
    )
    with (
        patch(
            "app.infrastructure.ai.image_service.ImageService.download_media_bytes",
            new_callable=AsyncMock, return_value=b"png-bytes",
        ),
        patch(
            "app.infrastructure.ai.image_service.save_media",
            return_value="local://animations/abc.mp4",
        ) as save,
        patch(
            "app.infrastructure.ai.image_service.OpenRouterVideoClient"
        ) as client_cls,
    ):
        client_cls.return_value.animate_image = AsyncMock(
            return_value=SimpleNamespace(
                job_id="job-1",
                video_bytes=b"mp4-bytes",
                content_type="video/mp4",
            )
        )
        result = await svc.maybe_animate_postcard(
            channel=_postcard_channel(animate=True),
            image_url="local://covers/x.png",
            article_title="День ВМФ",
        )

    assert result == "local://animations/abc.mp4"
    save.assert_called_once_with(b"mp4-bytes", "animations", ".mp4")


@pytest.mark.asyncio
async def test_maybe_animate_falls_back_to_mp4_when_gifski_missing() -> None:
    svc = ImageService(
        prompts=_prompts(),
        openrouter_api_key="or-key",
        postcard_animation_enabled=True,
        postcard_animation_as_gif=True,
    )
    with (
        patch("app.infrastructure.ai.image_service.ImageService.download_media_bytes", new_callable=AsyncMock, return_value=b"png"),
        patch(
            "app.infrastructure.ai.image_service.save_media",
            return_value="local://animations/abc.mp4",
        ) as save,
        patch("app.infrastructure.ai.image_service.OpenRouterVideoClient") as client_cls,
    ):
        client_cls.return_value.animate_image = AsyncMock(
            return_value=SimpleNamespace(
                job_id="job-1",
                video_bytes=b"mp4-bytes",
                content_type="video/mp4",
            )
        )
        result = await svc.maybe_animate_postcard(
            channel=_postcard_channel(animate=True),
            image_url="local://covers/x.png",
            article_title="День ВМФ",
        )

    assert result == "local://animations/abc.mp4"
    save.assert_called_once_with(b"mp4-bytes", "animations", ".mp4")


@pytest.mark.asyncio
async def test_maybe_animate_success_saves_video() -> None:
    svc = ImageService(
        prompts=_prompts(),
        openrouter_api_key="or-key",
        postcard_animation_enabled=True,
        postcard_animation_as_gif=False,
    )
    with (
        patch(
            "app.infrastructure.ai.image_service.ImageService.download_media_bytes",
            new_callable=AsyncMock, return_value=b"png-bytes",
        ),
        patch(
            "app.infrastructure.ai.image_service.save_media",
            return_value="local://animations/abc.mp4",
        ) as save,
        patch(
            "app.infrastructure.ai.image_service.OpenRouterVideoClient"
        ) as client_cls,
    ):
        client_cls.return_value.animate_image = AsyncMock(
            return_value=SimpleNamespace(
                job_id="job-1",
                video_bytes=b"mp4-bytes",
                content_type="video/mp4",
            )
        )
        result = await svc.maybe_animate_postcard(
            channel=_postcard_channel(animate=True),
            image_url="local://covers/x.png",
            article_title="День ВМФ",
        )

    assert result == "local://animations/abc.mp4"
    save.assert_called_once_with(b"mp4-bytes", "animations", ".mp4")


@pytest.mark.asyncio
async def test_maybe_animate_passes_configured_duration() -> None:
    svc = ImageService(
        prompts=_prompts(),
        openrouter_api_key="or-key",
        postcard_animation_enabled=True,
        postcard_animation_duration=3,
    )
    with (
        patch("app.infrastructure.ai.image_service.ImageService.download_media_bytes", new_callable=AsyncMock, return_value=b"png"),
        patch("app.infrastructure.ai.image_service.save_media", return_value="local://animations/x.mp4"),
        patch("app.infrastructure.ai.image_service.OpenRouterVideoClient") as client_cls,
    ):
        client_cls.return_value.animate_image = AsyncMock(
            return_value=SimpleNamespace(job_id="j", video_bytes=b"v", content_type="video/mp4")
        )
        await svc.maybe_animate_postcard(
            channel=_postcard_channel(animate=True),
            image_url="local://covers/x.png",
            article_title="День ВМФ",
        )
    assert client_cls.return_value.animate_image.await_args.kwargs["duration"] == 3
    assert client_cls.return_value.animate_image.await_args.kwargs["aspect_ratio"] == "1:1"


def _article_channel(*, animate: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        id=8,
        name="ПАРАГРАФ",
        topic="paragraph",
        animate_postcards=animate,
        image_prompt_guidelines="Scene: {scene}",
    )


@pytest.mark.asyncio
async def test_maybe_animate_works_for_article_channel() -> None:
    svc = ImageService(
        prompts=_prompts(),
        openrouter_api_key="or-key",
        postcard_animation_enabled=True,
    )
    with (
        patch("app.infrastructure.ai.image_service.ImageService.download_media_bytes", new_callable=AsyncMock, return_value=b"png"),
        patch("app.infrastructure.ai.image_service.save_media", return_value="local://animations/x.mp4"),
        patch("app.infrastructure.ai.image_service.OpenRouterVideoClient") as client_cls,
    ):
        client_cls.return_value.animate_image = AsyncMock(
            return_value=SimpleNamespace(
                job_id="job-2",
                video_bytes=b"mp4",
                content_type="video/mp4",
            )
        )
        result = await svc.maybe_animate_postcard(
            channel=_article_channel(animate=True),
            image_url="local://covers/x.png",
            article_title="Заголовок статьи",
        )
    assert result == "local://animations/x.mp4"
