"""Postcard image generation uses Responses with direct and Qwen fallbacks."""

import base64
import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import AsyncOpenAI

from app.domain.enums import ImageSource
from app.domain.platform_settings import is_valid_openai_model_name
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


def test_installed_openai_sdk_supports_responses_tool_budget() -> None:
    """Declared OpenAI minimum must support arguments used by production."""
    signature = inspect.signature(
        AsyncOpenAI(api_key="test").responses.create
    )

    assert "max_tool_calls" in signature.parameters


def test_invalid_orchestrator_model_falls_back_to_safe_default() -> None:
    svc = ImageService(
        prompts=_prompts(),
        postcard_orchestrator_model="invalid model name",
    )

    assert svc._postcard_orchestrator_model == "gpt-5.6"


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("gpt-5.6", True),
        ("gpt_5:preview", True),
        ("", False),
        ("gpt model", False),
        ("../gpt", False),
    ],
)
def test_openai_orchestrator_model_validation(model: str, expected: bool) -> None:
    assert is_valid_openai_model_name(model) is expected


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "output",
    [
        [],
        [SimpleNamespace(type="output_text", result=None)],
        [SimpleNamespace(type="image_generation_call", result="not-base64!")],
    ],
)
async def test_responses_invalid_outputs_return_none(
    output: list[SimpleNamespace],
) -> None:
    create = AsyncMock(return_value=SimpleNamespace(output=output))
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    client_context = MagicMock()
    client_context.__aenter__ = AsyncMock(return_value=client)
    client_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.infrastructure.ai.image_service.AsyncOpenAI",
        return_value=client_context,
    ):
        svc = ImageService(prompts=_prompts(), openai_db_key="test-key")
        result = await svc._generate_postcard_with_responses("Доброе утро")

    assert result is None


@pytest.mark.asyncio
async def test_responses_exception_returns_none_for_direct_fallback() -> None:
    create = AsyncMock(side_effect=TimeoutError("timed out"))
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    client_context = MagicMock()
    client_context.__aenter__ = AsyncMock(return_value=client)
    client_context.__aexit__ = AsyncMock(return_value=None)

    with patch(
        "app.infrastructure.ai.image_service.AsyncOpenAI",
        return_value=client_context,
    ):
        svc = ImageService(prompts=_prompts(), openai_db_key="test-key")
        result = await svc._generate_postcard_with_responses("Доброе утро")

    assert result is None


@pytest.mark.asyncio
async def test_postcard_responses_call_uses_high_quality_auto_image_tool() -> None:
    encoded = base64.b64encode(b"generated-png").decode("ascii")
    response = SimpleNamespace(
        output=[
            SimpleNamespace(
                type="image_generation_call",
                result=encoded,
            )
        ]
    )
    create = AsyncMock(return_value=response)
    client = SimpleNamespace(responses=SimpleNamespace(create=create))
    client_context = MagicMock()
    client_context.__aenter__ = AsyncMock(return_value=client)
    client_context.__aexit__ = AsyncMock(return_value=None)

    with (
        patch(
            "app.infrastructure.ai.image_service.AsyncOpenAI",
            return_value=client_context,
        ) as client_factory,
        patch(
            "app.infrastructure.ai.image_service.save_media",
            return_value="local://covers/postcard.png",
        ) as save,
    ):
        svc = ImageService(
            prompts=_prompts(),
            openai_db_key="test-key",
            postcard_orchestrator_model="gpt-5.6",
        )
        url = await svc._generate_postcard_with_responses(
            'Создай открытку с надписью «Доброго утра!»'
        )

    assert url == "local://covers/postcard.png"
    client_factory.assert_called_once_with(
        api_key="test-key",
        timeout=180.0,
        max_retries=1,
    )
    create.assert_awaited_once()
    call = create.await_args.kwargs
    assert call["model"] == "gpt-5.6"
    assert call["max_tool_calls"] == 1
    assert call["store"] is False
    assert call["tools"] == [
        {
            "type": "image_generation",
            "quality": "high",
            "size": "auto",
            "output_format": "png",
        }
    ]
    save.assert_called_once_with(b"generated-png", "covers", ".png")


@pytest.mark.asyncio
async def test_postcard_primary_path_preserves_greeting_text() -> None:
    svc = ImageService(prompts=_prompts())
    svc._generate_postcard_with_responses = AsyncMock(
        return_value="https://gen/postcard.png"
    )
    svc._generate_postcard_dalle_cover = AsyncMock(
        return_value="SHOULD_NOT_BE_CALLED"
    )
    svc._generate_with_qwen_constraints = AsyncMock(return_value="SHOULD_NOT_BE_CALLED")

    url, source = await svc.resolve_article_image(
        channel=_postcard_channel(),
        article_title="Доброе утро",
        topic="postcard",
        image_prompt="sunrise breakfast window, warm light",
        greeting_text="Доброго утра!",
    )

    assert (url, source) == ("https://gen/postcard.png", ImageSource.GENERATED.value)
    svc._generate_postcard_with_responses.assert_awaited_once()
    sent_prompt = svc._generate_postcard_with_responses.await_args.args[0]
    assert "Доброго утра!" in sent_prompt
    assert "sunrise breakfast window" in sent_prompt
    assert "Absolutely no text" not in sent_prompt
    svc._generate_postcard_dalle_cover.assert_not_awaited()
    svc._generate_with_qwen_constraints.assert_not_awaited()


@pytest.mark.asyncio
async def test_postcard_falls_back_to_direct_high_quality_cover() -> None:
    svc = ImageService(prompts=_prompts())
    svc._generate_postcard_with_responses = AsyncMock(return_value=None)
    svc._generate_postcard_dalle_cover = AsyncMock(
        return_value="https://gen/direct.png"
    )
    svc._generate_with_qwen_constraints = AsyncMock(return_value="SHOULD_NOT_BE_CALLED")

    url, source = await svc.resolve_article_image(
        channel=_postcard_channel(),
        article_title="Доброе утро",
        topic="postcard",
        image_prompt="sunrise breakfast window, warm light",
        greeting_text="Доброго утра!",
    )

    assert (url, source) == ("https://gen/direct.png", ImageSource.GENERATED.value)
    svc._generate_postcard_dalle_cover.assert_awaited_once()
    svc._generate_with_qwen_constraints.assert_not_awaited()


@pytest.mark.asyncio
async def test_direct_postcard_fallback_keeps_text_and_uses_portrait_high() -> None:
    svc = ImageService(prompts=_prompts())
    svc._call_openai_image = AsyncMock(return_value="https://gen/direct.png")

    url = await svc._generate_postcard_dalle_cover(
        'Открытка с надписью «Доброго утра!»'
    )

    assert url == "https://gen/direct.png"
    svc._call_openai_image.assert_awaited_once_with(
        'Открытка с надписью «Доброго утра!»',
        size="1024x1536",
        quality="high",
    )


@pytest.mark.asyncio
async def test_postcard_falls_back_to_qwen_after_openai_failures() -> None:
    svc = ImageService(prompts=_prompts())
    svc._generate_postcard_with_responses = AsyncMock(return_value=None)
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
