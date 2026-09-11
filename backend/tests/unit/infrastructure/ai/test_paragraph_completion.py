"""Регрессии завершённости публикаций ПАРАГРАФА."""

import json
from typing import Final

import pytest
from pytest_mock import MockerFixture

from app.domain.paragraph_validator import validate_paragraph_draft
from app.domain.prompt_defaults import PROMPT_DEFAULTS
from app.infrastructure.ai.article_writer import ArticleWriter, WriterPrompts
from app.infrastructure.ai.deepseek_client import DeepSeekClient
from app.infrastructure.models.channel import Channel

_POST_LIMIT: Final = 3600
_TITLE: Final = "История открытия 💡"
_ENDING: Final = "После расследования источник изолировали, а район очистили."


def _story(length: int) -> str:
    return ("Факт исследования. " * (length // 19)).rstrip() + "\n\n" + _ENDING


def _response(story: str) -> str:
    return json.dumps(
        {"title": _TITLE, "post_text": story, "body_html": story, "hook": "Начало."},
        ensure_ascii=False,
    )


def _prompts() -> WriterPrompts:
    fields = {
        "default_template": "writing.default",
        "postcard_template": "writing.postcard",
        "system_default": "writing.system_default",
        "system_devtools": "writing.system_devtools",
        "system_paragraph": "writing.system_paragraph",
        "system_postcard": "writing.system_postcard",
        "devtools_instructions": "writing.devtools_instructions",
        "paragraph_instructions": "writing.paragraph_instructions",
        "image_hint_default": "image.writer_hint_default",
        "image_hint_postcard": "image.writer_hint_postcard",
        "image_hint_paragraph": "image.writer_hint_paragraph",
    }
    return WriterPrompts(
        **{field: PROMPT_DEFAULTS[key].template_text for field, key in fields.items()}
    )


@pytest.mark.parametrize("story_length", [1600, 2600, 3400])
def test_parse_when_story_is_complete_should_preserve_ending(story_length: int) -> None:
    """Сохраняет развязку расширенного поста без отдельной длинной статьи."""
    story = _story(story_length)
    draft = ArticleWriter._parse_response(
        _response(story),
        _POST_LIMIT,
        900,
        channel=Channel(name="ПАРАГРАФ", topic="science"),
    )
    assert draft is not None
    assert story in draft.teaser
    assert draft.teaser.endswith(_ENDING)
    assert draft.body_html == ""


@pytest.mark.parametrize("truncated", [False, True])
def test_parse_when_output_is_unsafe_should_reject_not_cut(truncated: bool) -> None:
    """Не принимает превышение лимита и остановку генерации по токенам."""
    draft = ArticleWriter._parse_response(
        _response(_story(4000 if not truncated else 1800)),
        _POST_LIMIT,
        _POST_LIMIT,
        channel=Channel(name="ПАРАГРАФ", topic="science"),
        truncated=truncated,
    )
    assert draft is None


def test_parse_when_json_is_damaged_should_reject_partial_paragraph() -> None:
    """Не публикует поля, спасённые из незавершённого ответа модели."""
    draft = ArticleWriter._parse_response(
        _response(_story(1800))[:-1],
        _POST_LIMIT,
        _POST_LIMIT,
        channel=Channel(name="ПАРАГРАФ", topic="science"),
    )
    assert draft is None


@pytest.mark.parametrize("overflow", [0, 1])
def test_parse_when_at_assembled_limit_should_accept_only_complete_fit(
    overflow: int,
) -> None:
    """Учитывает заголовок и HTML при проверке границы публикации."""
    prefix = f"<b>{_TITLE}</b>\n\n"
    story = "я" * (_POST_LIMIT - len(prefix) - 1 + overflow) + "."
    draft = ArticleWriter._parse_response(
        _response(story),
        _POST_LIMIT,
        _POST_LIMIT,
        channel=Channel(name="ПАРАГРАФ", topic="science"),
    )
    assert (draft is None) is bool(overflow)


@pytest.mark.asyncio
async def test_write_when_paragraph_should_use_standalone_editorial_prompt(
    mocker: MockerFixture,
) -> None:
    """Передаёт исследование без противоречивых правил общего анонса."""
    client = mocker.create_autospec(DeepSeekClient, instance=True)
    client.chat_completion_with_meta.return_value = (_response(_story(1900)), "stop")
    writer = ArticleWriter(_prompts(), client=client)
    await writer.write(
        Channel(name="ПАРАГРАФ", topic="science", style_prompt="Для любознательных"),
        topic="История источника",
        angle="Последствия",
        research_context="Проверенные факты",
        body_max_length=7500,
        teaser_max_length=900,
    )
    prompt = client.chat_completion_with_meta.call_args.kwargs["user_prompt"]
    assert "Проверенные факты" in prompt
    assert "История источника" in prompt
    assert "Для любознательных" in prompt
    assert "без спойлеров" not in prompt
    assert "3-5 разделов" not in prompt
    assert "850–1400" not in prompt
    assert "3600" in prompt


@pytest.mark.asyncio
async def test_write_when_first_draft_overflows_should_retry_complete_story(
    mocker: MockerFixture,
) -> None:
    """Повторяет генерацию, а не публикует обрезанную первую попытку."""
    client = mocker.create_autospec(DeepSeekClient, instance=True)
    client.chat_completion_with_meta.side_effect = [
        (_response(_story(4200)), "stop"),
        (_response(_story(2100)), "stop"),
    ]
    draft = await ArticleWriter(_prompts(), client=client).write(
        Channel(name="ПАРАГРАФ", topic="science"),
        topic="Источник",
        angle="Последствия",
        research_context="Факты",
        body_max_length=7500,
        teaser_max_length=900,
    )
    assert client.chat_completion_with_meta.await_count == 2
    assert draft.teaser.endswith(_ENDING)


def test_validation_when_full_post_is_longer_should_accept_extended_format() -> None:
    """Разрешает расширенный законченный пост без двойного учёта заголовка."""
    result = validate_paragraph_draft(
        title=_TITLE,
        teaser=f"<b>{_TITLE}</b>\n\n🔎 {_story(3200)}",
        body_html="",
    )
    assert result.ok, result.blocking_messages


@pytest.mark.parametrize(
    "key",
    [
        "writing.system_paragraph",
        "writing.paragraph_instructions",
        "ideation.system_paragraph",
    ],
)
def test_prompts_when_paragraph_should_require_outcome_research(key: str) -> None:
    """Фиксирует требование последствий в авторском и поисковом задании."""
    prompt = PROMPT_DEFAULTS[key].template_text.lower()
    assert "последств" in prompt
    assert "источник" in prompt or "исследован" in prompt


def test_parse_when_only_body_is_returned_should_keep_full_story() -> None:
    """Сохраняет полное тело, если модель не продублировала поле post_text."""
    story = _story(2400)
    response = json.dumps({"title": _TITLE, "body_html": story, "hook": "Начало."})
    draft = ArticleWriter._parse_response(
        response, _POST_LIMIT, 900, channel=Channel(name="ПАРАГРАФ", topic="science")
    )
    assert draft is not None
    assert draft.teaser.endswith(_ENDING)


@pytest.mark.asyncio
async def test_write_when_both_attempts_overflow_should_raise_domain_error(
    mocker: MockerFixture,
) -> None:
    """Блокирует публикацию, если обе попытки не дают целого поста в лимите."""
    from app.domain.article_errors import ArticleGenerationError

    client = mocker.create_autospec(DeepSeekClient, instance=True)
    client.chat_completion_with_meta.return_value = (_response(_story(4200)), "stop")
    with pytest.raises(ArticleGenerationError):
        await ArticleWriter(_prompts(), client=client).write(
            Channel(name="ПАРАГРАФ", topic="science"),
            topic="Источник",
            angle="Последствия",
            research_context="Факты",
            body_max_length=7500,
            teaser_max_length=900,
        )
    assert client.chat_completion_with_meta.await_count == 2
