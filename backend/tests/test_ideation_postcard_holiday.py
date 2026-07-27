"""Тест: идеация открыток форсирует официальный праздник, если он сегодня."""

from datetime import date
from typing import Any

import pytest

from app.domain.prompt_defaults import PROMPT_DEFAULTS
from app.infrastructure.ai.topic_ideation import IdeationPrompts, TopicIdeationService
from app.infrastructure.models.channel import Channel


def _ideation_prompts() -> IdeationPrompts:
    return IdeationPrompts(
        default_template=PROMPT_DEFAULTS["ideation.default"].template_text,
        postcard_template=PROMPT_DEFAULTS["ideation.postcard"].template_text,
        manual_topic_template=PROMPT_DEFAULTS["ideation.manual_topic"].template_text,
        manual_postcard_template=PROMPT_DEFAULTS["ideation.manual_postcard"].template_text,
        system_default=PROMPT_DEFAULTS["ideation.system_default"].template_text,
        system_postcard=PROMPT_DEFAULTS["ideation.system_postcard"].template_text,
        system_paragraph=PROMPT_DEFAULTS["ideation.system_paragraph"].template_text,
        devtools_extra=PROMPT_DEFAULTS["ideation.devtools_extra"].template_text,
        devtools_with_repos=PROMPT_DEFAULTS[
            "ideation.devtools_with_repos"
        ].template_text,
        devtools_no_repos=PROMPT_DEFAULTS["ideation.devtools_no_repos"].template_text,
        paragraph_extra=PROMPT_DEFAULTS["ideation.paragraph_extra"].template_text,
    )


def _postcard_channel() -> Channel:
    return Channel(
        id=13,
        name="Открытки от души | На любой случай",
        platform="max",
        platform_id="chat123",
        topic="postcard",
        content_mode="article",
        style_prompt="тёплые открытки на все случаи",
    )


class _CapturingClient:
    """DeepSeek-заглушка, запоминающая последний user_prompt."""

    def __init__(self, topic_json: str) -> None:
        self.last_user_prompt: str | None = None
        self._topic_json = topic_json

    async def chat_completion(self, **kwargs: Any) -> str:
        self.last_user_prompt = kwargs["user_prompt"]
        return self._topic_json


@pytest.mark.asyncio
async def test_prompt_forces_holiday_topic_when_today_is_a_holiday(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.infrastructure.ai.topic_ideation.date",
        type("FixedDate", (), {"today": staticmethod(lambda: date(2026, 3, 8))}),
    )
    client = _CapturingClient(
        '{"topic": "Международный женский день", '
        '"angle": "tulips flower shop, spring warmth", "search_queries": []}'
    )
    svc = TopicIdeationService(_ideation_prompts(), client=client)

    plan = await svc.plan_topic(_postcard_channel(), recent_topics=[])

    assert client.last_user_prompt is not None
    assert "Праздник сегодня: Международный женский день" in client.last_user_prompt
    assert "используй именно его" in client.last_user_prompt
    assert plan.topic == "Международный женский день"


@pytest.mark.asyncio
async def test_prompt_leaves_holiday_slot_empty_on_ordinary_day(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.infrastructure.ai.topic_ideation.date",
        type("FixedDate", (), {"today": staticmethod(lambda: date(2026, 7, 26))}),
    )
    client = _CapturingClient(
        '{"topic": "Доброе утро", "angle": "sunrise breakfast, warm", "search_queries": []}'
    )
    svc = TopicIdeationService(_ideation_prompts(), client=client)

    await svc.plan_topic(_postcard_channel(), recent_topics=[])

    assert client.last_user_prompt is not None
    assert "Праздник сегодня: \n" in client.last_user_prompt
    assert "подходящий текущему сезону" not in client.last_user_prompt
