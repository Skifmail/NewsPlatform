"""Контракт проверяемого результата генерации."""

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from app.domain.supplements import SupplementError
from app.infrastructure.search.tavily_client import TavilySearchResult
from app.services.supplement_generator import SupplementGenerator


@pytest.mark.parametrize("url", ["https://invented.org/x", "javascript:alert(1)"])
async def test_generate_when_model_invents_source_should_fail(
    mocker: MockerFixture, url: str
) -> None:
    """Источники ответа должны присутствовать в реальном поиске."""
    ai = AsyncMock()
    ai.chat_completion.side_effect = [
        json.dumps({"queries": ["кварц физика"]}),
        json.dumps(
            {
                "title": "Кварц",
                "text": "Кварц обладает пьезоэффектом.",
                "source_urls": [url],
                "reason": "Бытовая физика",
                "image_prompt": "Кристалл кварца крупным планом",
            }
        ),
    ]
    search = AsyncMock()
    search.search.return_value = [
        TavilySearchResult("Кварц", "https://nasa.gov/x", "Кварц")
    ]
    with pytest.raises(SupplementError):
        await SupplementGenerator(ai, search).generate(
            "fact", "Физика", [], {}, datetime.now(UTC)
        )


async def test_generate_when_news_has_no_dated_sources_should_fallback(
    mocker: MockerFixture,
) -> None:
    """Недатированные новости не выдаются за свежие."""
    ai = AsyncMock()
    ai.chat_completion.side_effect = [
        json.dumps({"queries": ["новая физика"]}),
        json.dumps({"queries": ["кварц"]}),
        json.dumps(
            {
                "title": "Кварц",
                "text": "Кварц обладает пьезоэффектом.",
                "source_urls": ["https://nasa.gov/x"],
                "reason": "Физика",
                "image_prompt": "Кристалл кварца крупным планом",
            }
        ),
    ]
    search = AsyncMock()
    search.search.return_value = [
        TavilySearchResult("Кварц", "https://nasa.gov/x", "Кварц")
    ]
    result = await SupplementGenerator(ai, search).generate(
        "news", "Наука", [], {}, datetime.now(UTC)
    )
    assert result["kind"] == "fact"
    assert result["fallback_reason"]


async def test_generate_when_search_fails_should_not_fallback(
    mocker: MockerFixture,
) -> None:
    """Сбой поиска не маскируется заменой новости фактом."""
    ai = AsyncMock()
    ai.chat_completion.return_value = json.dumps({"queries": ["наука"]})
    search = AsyncMock()
    search.search.side_effect = RuntimeError("Search failed")
    with pytest.raises(SupplementError):
        await SupplementGenerator(ai, search).generate(
            "news", "Наука", [], {}, datetime.now(UTC)
        )
    assert ai.chat_completion.await_count == 1


async def test_generate_when_fresh_news_should_preserve_sources_and_prompts() -> None:
    """Подтверждённая свежая новость сохраняет проверяемый журнал."""
    now = datetime(2026, 9, 12, 12, tzinfo=UTC)
    ai = AsyncMock()
    ai.chat_completion.side_effect = [
        json.dumps({"queries": ["новое исследование кварца"]}),
        json.dumps(
            {
                "title": "Кварцевый датчик",
                "text": (
                    "Учёные испытали новый кварцевый датчик. "
                    "Пока это лабораторный прототип."
                ),
                "source_urls": ["https://example.org/research"],
                "reason": "Понятная инженерия",
                "image_prompt": "Небольшой кварцевый датчик в лаборатории",
            }
        ),
    ]
    search = AsyncMock()
    search.search.return_value = [
        TavilySearchResult(
            "Датчик",
            "https://example.org/research",
            "Лабораторный опыт",
            published_date="2026-09-11T12:00:00Z",
        )
    ]
    result = await SupplementGenerator(ai, search).generate(
        "news", "Наука", [], {}, now
    )
    assert result["kind"] == "news"
    assert result["sources"][0]["published_date"] == "2026-09-11T12:00:00Z"
    assert "и что?" in result["trace"]["writing_prompt"]
    assert "это только модель" in result["trace"]["writing_prompt"]
    assert result["trace"]["writing_prompt"]
    assert result["trace"]["selection_reason"] == "Понятная инженерия"
    assert result["image_prompt"] == "Небольшой кварцевый датчик в лаборатории"
    search.search.assert_awaited_once_with(
        "новое исследование кварца", time_range="week"
    )


async def test_generate_when_text_is_complex_should_rewrite_plainly() -> None:
    """Сложный первый вариант переписывается без повторного поиска."""
    ai = AsyncMock()
    ai.chat_completion.side_effect = [
        json.dumps({"queries": ["эффект Холла исследование"]}),
        json.dumps(
            {
                "title": "Эффект Холла",
                "text": (
                    "Физики обнаружили аномальный эффект Холла в плоскости "
                    "низкоразмерной системы, показав, что электрический отклик "
                    "возникает при параллельном магнитном поле, что меняет "
                    "столетнее представление."
                ),
                "source_urls": ["https://example.org/hall"],
                "reason": "Неожиданный результат",
                "image_prompt": "Лабораторная установка с магнитом",
            }
        ),
        json.dumps(
            {
                "title": "Магнитное поле удивило физиков",
                "text": (
                    "Электрический ток повёл себя необычно, когда магнитное поле "
                    "направили вдоль тонкого материала."
                ),
                "source_urls": ["https://example.org/hall"],
                "reason": "Тот же факт простыми словами",
                "image_prompt": "Тонкий материал между полюсами магнита",
            }
        ),
    ]
    search = AsyncMock()
    search.search.return_value = [
        TavilySearchResult(
            "Hall effect",
            "https://example.org/hall",
            "Researchers measured an in-plane anomalous Hall effect.",
        )
    ]

    result = await SupplementGenerator(ai, search).generate(
        "fact", "Наука простыми словами", [], {}, datetime.now(UTC)
    )

    assert result["text"].startswith("Электрический ток повёл себя необычно")
    assert result["image_prompt"] == "Тонкий материал между полюсами магнита"
    assert ai.chat_completion.await_count == 3
    search.search.assert_awaited_once()


async def test_generate_when_model_wraps_json_in_markdown_should_accept_response() -> (
    None
):
    """JSON в Markdown-блоке не должен останавливать подготовку материала."""
    ai = AsyncMock()
    ai.chat_completion.side_effect = [
        '```json\n{"queries": ["кварц физика"]}\n```',
        "```json\n"
        + json.dumps(
            {
                "title": "Кварц",
                "text": (
                    "Кварц создаёт электрический заряд при сжатии, поэтому его "
                    "используют в точных датчиках давления."
                ),
                "source_urls": ["https://example.org/quartz"],
                "reason": "Понятный бытовой пример",
                "image_prompt": "Кристалл кварца рядом с датчиком давления",
            },
            ensure_ascii=False,
        )
        + "\n```",
    ]
    search = AsyncMock()
    search.search.return_value = [
        TavilySearchResult(
            "Quartz",
            "https://example.org/quartz",
            "Quartz produces an electric charge under mechanical stress.",
        )
    ]

    result = await SupplementGenerator(ai, search).generate(
        "fact", "Наука простыми словами", [], {}, datetime.now(UTC)
    )

    assert result["title"] == "Кварц"
    assert ai.chat_completion.await_count == 2


async def test_generate_when_reasoning_precedes_json_should_accept_response() -> None:
    """Служебное рассуждение модели не должно скрывать готовый JSON-объект."""
    ai = AsyncMock()
    ai.chat_completion.side_effect = [
        '<think>Подбираю тему</think>\n{"queries": ["кварц физика"]}',
        json.dumps(
            {
                "title": "Кварц",
                "text": (
                    "Кварц создаёт электрический заряд при сжатии, поэтому его "
                    "используют в точных датчиках давления."
                ),
                "source_urls": ["https://example.org/quartz"],
                "reason": "Понятный бытовой пример",
                "image_prompt": "Кристалл кварца рядом с датчиком давления",
            },
            ensure_ascii=False,
        ),
    ]
    search = AsyncMock()
    search.search.return_value = [
        TavilySearchResult(
            "Quartz",
            "https://example.org/quartz",
            "Quartz produces an electric charge under mechanical stress.",
        )
    ]

    result = await SupplementGenerator(ai, search).generate(
        "fact", "Наука простыми словами", [], {}, datetime.now(UTC)
    )

    assert result["title"] == "Кварц"
    assert ai.chat_completion.await_count == 2


async def test_generate_when_writing_json_is_invalid_should_retry_once() -> None:
    """Повреждённый ответ модели должен быть повторно запрошен один раз."""
    ai = AsyncMock()
    ai.chat_completion.side_effect = [
        json.dumps({"queries": ["кварц физика"]}),
        '{"title": "Кварц", "text":',
        json.dumps(
            {
                "title": "Кварц",
                "text": (
                    "Кварц создаёт электрический заряд при сжатии, поэтому его "
                    "используют в точных датчиках давления."
                ),
                "source_urls": ["https://example.org/quartz"],
                "reason": "Понятный бытовой пример",
                "image_prompt": "Кристалл кварца рядом с датчиком давления",
            }
        ),
    ]
    search = AsyncMock()
    search.search.return_value = [
        TavilySearchResult(
            "Quartz",
            "https://example.org/quartz",
            "Quartz produces an electric charge under mechanical stress.",
        )
    ]

    result = await SupplementGenerator(ai, search).generate(
        "fact", "Наука простыми словами", [], {}, datetime.now(UTC)
    )

    assert result["title"] == "Кварц"
    assert result["trace"]["writing_json_retry"] is True
    assert "валидный JSON-объект" in ai.chat_completion.await_args_list[2].args[1]
    assert ai.chat_completion.await_count == 3


async def test_generate_when_json_is_invalid_twice_should_fail_safely() -> None:
    """Два повреждённых ответа не должны приводить к поиску или публикации."""
    ai = AsyncMock()
    ai.chat_completion.side_effect = ["не json", '{"queries": [']
    search = AsyncMock()

    with pytest.raises(SupplementError, match="дважды вернула некорректный JSON"):
        await SupplementGenerator(ai, search).generate(
            "fact", "Наука простыми словами", [], {}, datetime.now(UTC)
        )

    assert ai.chat_completion.await_count == 2
    search.search.assert_not_awaited()


async def test_generate_when_requesting_json_should_use_fast_model_and_large_budget(
    mocker: MockerFixture,
) -> None:
    """Короткий JSON не должен обрезаться из-за рассуждений основной модели."""
    settings = mocker.patch("app.services.supplement_generator.get_settings")
    settings.return_value.deepseek_fast_model = "deepseek-fast-test"
    ai = AsyncMock()
    ai.chat_completion.side_effect = [
        json.dumps({"queries": ["кварц физика"]}),
        json.dumps(
            {
                "title": "Кварц",
                "text": (
                    "Кварц создаёт электрический заряд при сжатии, поэтому его "
                    "используют в точных датчиках давления."
                ),
                "source_urls": ["https://example.org/quartz"],
                "reason": "Понятный бытовой пример",
                "image_prompt": "Кристалл кварца рядом с датчиком давления",
            }
        ),
    ]
    search = AsyncMock()
    search.search.return_value = [
        TavilySearchResult(
            "Quartz",
            "https://example.org/quartz",
            "Quartz produces an electric charge under mechanical stress.",
        )
    ]

    await SupplementGenerator(ai, search).generate(
        "fact", "Наука простыми словами", [], {}, datetime.now(UTC)
    )

    for request in ai.chat_completion.await_args_list:
        assert request.kwargs["model"] == "deepseek-fast-test"
        assert request.kwargs["max_tokens"] >= 8000
        assert request.kwargs["temperature"] <= 0.3


async def test_generate_when_simplification_is_invalid_should_retry_plain_text() -> (
    None
):
    """Повторно сложный факт должен получить ещё одну безопасную редактуру."""
    source_url = "https://example.org/quartz"
    common = {
        "title": "Кварц",
        "source_urls": [source_url],
        "reason": "Понятный бытовой пример",
        "image_prompt": "Кристалл кварца рядом с датчиком давления",
    }
    ai = AsyncMock()
    ai.chat_completion.side_effect = [
        json.dumps({"queries": ["кварц физика"]}),
        json.dumps(
            {
                **common,
                "text": "Кварц создаёт электрический заряд. Его применяют в датчиках.",
            }
        ),
        json.dumps(
            {
                **common,
                "text": "Кварц реагирует на сжатие. Так работают точные датчики.",
            }
        ),
        json.dumps(
            {
                **common,
                "text": (
                    "Кварц создаёт электрический заряд при сжатии, поэтому его "
                    "используют в точных датчиках давления."
                ),
            }
        ),
    ]
    search = AsyncMock()
    search.search.return_value = [
        TavilySearchResult(
            "Quartz",
            source_url,
            "Quartz produces an electric charge under mechanical stress.",
        )
    ]

    result = await SupplementGenerator(ai, search).generate(
        "fact", "Наука простыми словами", [], {}, datetime.now(UTC)
    )

    assert result["text"].startswith("Кварц создаёт электрический заряд при сжатии")
    assert result["trace"]["plain_language_attempts"] == 2
    assert ai.chat_completion.await_count == 4
