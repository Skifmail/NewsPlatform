"""Тест: генерация обложки открытки идёт через gpt-image-2 с сохранённой кириллицей,
с фолбэком на Qwen (без текста) при неудаче primary-пути."""

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
    return ImageGenPrompts(
        no_text_negative="text, letters, cyrillic",
        news_negative="portrait, face",
        cover_template="Cover: {title} {summary}",
        postcard_cover_template=(
            'Scene: {scene}. Occasion: "{title}". '
            'Russian text reading: "{greeting_text}".'
        ),
    )


@pytest.mark.asyncio
async def test_postcard_primary_path_uses_dalle_with_greeting_text() -> None:
    svc = ImageService(prompts=_prompts())
    svc._generate_with_dalle_primary = AsyncMock(return_value="https://gen/postcard.png")
    svc._generate_with_qwen_constraints = AsyncMock(return_value="SHOULD_NOT_BE_CALLED")

    url, source = await svc.resolve_article_image(
        channel=_postcard_channel(),
        article_title="Доброе утро",
        topic="postcard",
        image_prompt="sunrise breakfast window, warm light",
        greeting_text="Доброго утра!",
    )

    assert (url, source) == ("https://gen/postcard.png", ImageSource.GENERATED.value)
    svc._generate_with_dalle_primary.assert_awaited_once()
    sent_prompt = svc._generate_with_dalle_primary.await_args.args[0]
    assert "Доброго утра!" in sent_prompt
    assert "sunrise breakfast window" in sent_prompt
    svc._generate_with_qwen_constraints.assert_not_awaited()


@pytest.mark.asyncio
async def test_postcard_falls_back_to_qwen_without_text_on_dalle_failure() -> None:
    svc = ImageService(prompts=_prompts())
    svc._generate_with_dalle_primary = AsyncMock(return_value=None)
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
