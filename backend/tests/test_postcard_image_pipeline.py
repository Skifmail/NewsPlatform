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
async def test_direct_postcard_cover_keeps_text_and_uses_square_high() -> None:
    svc = ImageService(prompts=_prompts())
    svc._call_openai_image = AsyncMock(return_value="https://gen/direct.png")

    url = await svc._generate_postcard_dalle_cover(
        'Открытка с надписью «Доброго утра!»'
    )

    assert url == "https://gen/direct.png"
    svc._call_openai_image.assert_awaited_once_with(
        'Открытка с надписью «Доброго утра!»',
        size="1024x1024",
        quality="high",
    )


@pytest.mark.asyncio
async def test_postcard_falls_back_to_qwen_after_openai_failure() -> None:
    svc = ImageService(prompts=_prompts())
    svc._generate_postcard_dalle_cover = AsyncMock(return_value=None)
    svc._generate_with_qwen_constraints = AsyncMock(return_value="https://gen/fallback.png")

    url, source = await svc.resolve_article_image(
        channel=_postcard_channel(),
        article_title="Доброе утро",
        topic="postcard",
        image_prompt="sunrise breakfast window, warm light",
        greeting_text="Доброго утра!",
    )

    assert (url, source) == ("https://gen/fallback.png", ImageSource.GENERATED.value)
    svc._generate_with_qwen_constraints.assert_awaited_once()
