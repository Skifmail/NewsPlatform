"""Тесты ручной темы/повода для ideation service."""

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


class _CapturingClient:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.last_user_prompt: str | None = None
        self.last_system_prompt: str | None = None

    async def chat_completion(self, **kwargs: Any) -> str:
        self.last_user_prompt = kwargs["user_prompt"]
        self.last_system_prompt = kwargs["system_prompt"]
        return self.payload


def _article_channel() -> Channel:
    return Channel(
        id=21,
        name="Открытия и факты",
        platform="telegram",
        platform_id="facts123",
        topic="science",
        content_mode="article",
        style_prompt="короткие, яркие познавательные статьи",
    )


def _postcard_channel() -> Channel:
    return Channel(
        id=22,
        name="Открытки от души",
        platform="max",
        platform_id="cards123",
        topic="postcard",
        content_mode="article",
        style_prompt="тёплые душевные открытки",
    )


@pytest.mark.asyncio
async def test_manual_article_topic_keeps_user_text_and_builds_queries() -> None:
    client = _CapturingClient(
        '{"topic": "другая тема", "angle": "объяснить феномен простым языком", '
        '"search_queries": ["эффект плацебо история", "эффект плацебо исследования", '
        '"эффект плацебо факты"]}'
    )
    svc = TopicIdeationService(_ideation_prompts(), client=client)

    plan = await svc.plan_manual_topic(_article_channel(), "Эффект плацебо")

    assert plan.topic == "Эффект плацебо"
    assert plan.angle == "объяснить феномен простым языком"
    assert plan.search_queries == [
        "эффект плацебо история",
        "эффект плацебо исследования",
        "эффект плацебо факты",
    ]
    assert client.last_user_prompt is not None
    assert "Тема статьи ЗАДАНА вручную редактором" in client.last_user_prompt
    assert "Эффект плацебо" in client.last_user_prompt
    assert (
        client.last_system_prompt
        == PROMPT_DEFAULTS["ideation.system_default"].template_text
    )


@pytest.mark.asyncio
async def test_manual_postcard_topic_uses_postcard_prompt_and_system(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.infrastructure.ai.topic_ideation.date",
        type("FixedDate", (), {"today": staticmethod(lambda: date(2026, 12, 30))}),
    )
    client = _CapturingClient(
        '{"topic": "Новый год", "angle": "gift boxes confetti golden lights", '
        '"search_queries": []}'
    )
    svc = TopicIdeationService(_ideation_prompts(), client=client)

    plan = await svc.plan_manual_topic(_postcard_channel(), "С днем рождения")

    assert plan.topic == "С днем рождения"
    assert plan.angle == "gift boxes confetti golden lights"
    assert plan.search_queries == []
    assert client.last_user_prompt is not None
    assert "Редактор задал повод, его нельзя менять" in client.last_user_prompt
    assert "Сегодня 30.12.2026" in client.last_user_prompt
    assert (
        client.last_system_prompt
        == PROMPT_DEFAULTS["ideation.system_postcard"].template_text
    )
