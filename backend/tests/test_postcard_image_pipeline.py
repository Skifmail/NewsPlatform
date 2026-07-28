"""Postcard image generation uses direct gpt-image-2 with Qwen fallback."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.enums import ImageSource
from app.infrastructure.ai.image_service import ImageGenPrompts, ImageService


def _postcard_channel() -> SimpleNamespace:
    return SimpleNamespace(
        id=13,
        name="Открытки от души | На любой случай",
        topic="postcard",
        image_prompt_guidelines=(
            "A beautiful artistic greeting card for the occasion. {scene} "
            "No text, no letters, no numbers, no faces, no people."
        ),
    )


def _prompts() -> ImageGenPrompts:
    """Test prompts: postcard cover mirrors ChatGPT one-liner default."""
    return ImageGenPrompts(
        no_text_negative="text, letters, cyrillic",
        news_negative="portrait, face",
        cover_template="Cover: {title} {summary}",
        postcard_cover_template="Сделай открытку поздравление с {title}",
    )


@pytest.mark.asyncio
async def test_postcard_primary_path_sends_simple_request_to_gpt_image() -> None:
    svc = ImageService(prompts=_prompts())
    svc._generate_postcard_dalle_cover = AsyncMock(
        return_value="https://gen/postcard.png"
    )
    svc._generate_with_qwen_constraints = AsyncMock(return_value="SHOULD_NOT_BE_CALLED")

    url, source = await svc.resolve_article_image(
        channel=_postcard_channel(),
        article_title="День работника МФЦ",
        topic="postcard",
        image_prompt="unused scene from writer",
        greeting_text="unused greeting",
    )

    assert (url, source) == ("https://gen/postcard.png", ImageSource.GENERATED.value)
    svc._generate_postcard_dalle_cover.assert_awaited_once()
    sent_prompt = svc._generate_postcard_dalle_cover.await_args.args[0]
    assert sent_prompt == "Сделай открытку поздравление с День работника МФЦ"
    assert "unused scene" not in sent_prompt
    assert "unused greeting" not in sent_prompt
    assert "Absolutely no text" not in sent_prompt
    assert "логотип" not in sent_prompt.lower()
    svc._generate_with_qwen_constraints.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_postcard_cover_uses_configured_openai_quality() -> None:
    svc = ImageService(prompts=_prompts(), openai_image_quality="medium")
    svc._call_cover_image = AsyncMock(return_value="https://gen/direct.png")

    url = await svc._generate_postcard_dalle_cover(
        'Открытка с надписью «Доброго утра!»'
    )

    assert url == "https://gen/direct.png"
    svc._call_cover_image.assert_awaited_once_with(
        'Открытка с надписью «Доброго утра!»',
        size="1024x1024",
    )


@pytest.mark.asyncio
async def test_cover_image_routes_to_openrouter_when_configured() -> None:
    svc = ImageService(
        prompts=_prompts(),
        cover_image_provider="openrouter",
        openrouter_api_key="sk-or-test",
        openrouter_image_model="bytedance-seed/seedream-4.5",
    )
    svc._call_openrouter_image = AsyncMock(return_value="https://gen/seedream.png")

    url = await svc._call_cover_image("Test prompt", size="1024x1024", quality="high")

    assert url == "https://gen/seedream.png"
    svc._call_openrouter_image.assert_awaited_once_with(
        "Test prompt",
        size="1024x1024",
    )


@pytest.mark.asyncio
async def test_postcard_falls_back_to_qwen_after_openai_failure() -> None:
    svc = ImageService(prompts=_prompts())
    svc._generate_postcard_dalle_cover = AsyncMock(return_value=None)
    svc._generate_with_qwen_constraints = AsyncMock(return_value="https://gen/fallback.png")
    svc._persist_remote_cover = AsyncMock(return_value="local://covers/fallback.png")

    url, source = await svc.resolve_article_image(
        channel=_postcard_channel(),
        article_title="День крещения Руси",
        topic="postcard",
        image_prompt="sunrise breakfast window, warm light",
        greeting_text="Доброго утра!",
    )

    assert (url, source) == ("local://covers/fallback.png", ImageSource.GENERATED.value)
    svc._generate_with_qwen_constraints.assert_awaited_once_with(
        "Сделай открытку поздравление с День крещения Руси"
    )
    # Writer scene must NOT replace the gpt-image cover prompt on fallback.
    sent = svc._generate_with_qwen_constraints.await_args.args[0]
    assert "sunrise" not in sent
    assert "День крещения Руси" in sent
    svc._persist_remote_cover.assert_awaited_once()
