"""Тесты очереди тем, валидатора Параграфа и клавиатуры MAX.

Callers: pytest. Covers topic_queue, paragraph_validator, max_keyboard.
User: implement expert recommendations for Параграф MAX automatically.
"""

from app.domain.paragraph_validator import validate_paragraph_draft
from app.domain.topic_dedup import is_topic_too_similar
from app.domain.topic_queue import (
    append_topics,
    mark_published,
    next_pending,
    parse_topic_queue,
    parse_topics_from_text,
    serialize_topic_queue,
)
from app.infrastructure.ai.paragraph_teaser_formatter import (
    build_paragraph_teaser,
    uses_editorial_topic_queue,
)
from app.infrastructure.publishers.max_keyboard import (
    build_callback_keyboard,
    parse_callback_payload,
)


def test_parse_topics_from_numbered_list() -> None:
    raw = """
    1. Космический аппарат NASA
    - Почему иллюминаторы круглые
    Медицинский аппарат
    """
    topics = parse_topics_from_text(raw)
    assert topics == [
        "Космический аппарат NASA",
        "Почему иллюминаторы круглые",
        "Медицинский аппарат",
    ]


def test_topic_queue_lifecycle() -> None:
    items = append_topics([], ["Тема A", "Тема B"])
    assert next_pending(items).title == "Тема A"
    items = mark_published(items, items[0].id, published_post_id=42)
    assert items[0].status == "published"
    assert items[0].published_post_id == 42
    assert next_pending(items).title == "Тема B"
    raw = serialize_topic_queue(items)
    restored = parse_topic_queue(raw)
    assert len(restored) == 2
    assert restored[0].status == "published"


def test_bombardier_entity_dedup() -> None:
    recent = ["Жук-бомбардир: живой огнемёт"]
    assert is_topic_too_similar(
        "Bombardier beetle и химическая защита", recent
    )


def test_validator_catches_offtopic_and_broken_html() -> None:
    bad = validate_paragraph_draft(
        title="Язык запросов 1С",
        teaser="Про SQL",
        body_html='Текст <a href="https://www.',
    )
    assert not bad.ok
    codes = {i.code for i in bad.issues}
    assert "off_topic" in codes
    assert "broken_html" in codes or "incomplete_sentence" in codes


def test_validator_rejects_predstav_opener() -> None:
    result = validate_paragraph_draft(
        title="Факт 💡",
        teaser="Представь, что жук стреляет кипятком. " * 20,
        body_html="История закончена нормально.",
    )
    assert any(i.code == "forbidden_opener" for i in result.issues)


def test_paragraph_teaser_skips_english_quote() -> None:
    teaser = build_paragraph_teaser(
        {
            "title": "Креветка",
            "hook": "Креветка создаёт вспышку света.",
            "quote": "These are insanely high accelerations.",
            "interaction_question": "Удивило?",
        },
        teaser_max_length=900,
    )
    assert "These are insanely" not in teaser
    assert "Удивило?" in teaser


def test_max_keyboard_payload() -> None:
    kb = build_callback_keyboard(["Да", "Нет"], payload_prefix="pq:15")
    assert kb is not None
    assert kb["type"] == "inline_keyboard"
    buttons = kb["payload"]["buttons"][0]
    assert buttons[0]["payload"] == "pq:15:0"
    post_id, idx = parse_callback_payload("pq:15:1")
    assert post_id == 15 and idx == 1


def test_editorial_queue_only_for_paragraph_max() -> None:
    assert uses_editorial_topic_queue("Параграф (МАКС)", "max") is True
    assert uses_editorial_topic_queue("ПАРАГРАФ (ВК)", "vk") is False
    assert uses_editorial_topic_queue("Другой канал", "max") is False


def test_validator_rejects_machine_metric_conversion() -> None:
    """8000 ft → 2438 м выглядит как слепой перевод."""
    body = (
        "Давление в салоне соответствует высоте около 2438 метров над уровнем моря. "
        "Это сделано для комфорта пассажиров и экипажа. "
    ) * 3
    result = validate_paragraph_draft(
        title="Дверь самолёта ✈️",
        teaser=body,
        body_html="История закончена нормально.",
    )
    codes = {i.code for i in result.issues}
    assert "unnatural_metric" in codes


def test_validator_rejects_imperial_units() -> None:
    body = (
        "Кабина держит давление как на высоте 8000 футов — так устроены почти все лайнеры. "
        "Это сделано для комфорта пассажиров и экипажа в длительном полёте. "
    ) * 3
    result = validate_paragraph_draft(
        title="Дверь самолёта ✈️",
        teaser=body,
        body_html="История закончена нормально.",
    )
    assert any(i.code == "imperial_units" for i in result.issues)


def test_validator_allows_natural_metric() -> None:
    body = (
        "✈️ Давление в салоне соответствует высоте около 2400 метров. "
        "Так устроены почти все пассажирские лайнеры для комфорта. "
    ) * 4
    result = validate_paragraph_draft(
        title="Дверь самолёта ✈️",
        teaser=body,
        body_html="История закончена нормально 💡 Почему дверь не открыть в полёте?",
        interaction_question="Знал об этом?",
        button_options=["Знал", "Теперь знаю"],
    )
    codes = {i.code for i in result.issues}
    assert "unnatural_metric" not in codes
    assert "imperial_units" not in codes


def test_validator_requires_emoji() -> None:
    body = (
        "Давление в салоне соответствует высоте около 2400 метров. "
        "Так устроены почти все пассажирские лайнеры для комфорта. "
    ) * 4
    result = validate_paragraph_draft(
        title="Дверь самолёта без эмодзи",
        teaser=body,
        body_html="История закончена нормально.",
        interaction_question="Знал?",
        button_options=["Да", "Нет"],
    )
    assert any(i.code == "missing_emoji" for i in result.issues)


def test_validator_accepts_title_emoji() -> None:
    body = (
        "✈️ Давление в салоне соответствует высоте около 2400 метров. "
        "Так устроены почти все пассажирские лайнеры для комфорта. "
    ) * 4
    result = validate_paragraph_draft(
        title="Дверь самолёта ✈️",
        teaser=body,
        body_html="История закончена нормально 💡",
        interaction_question="Знал?",
        button_options=["Да", "Нет"],
    )
    assert not any(i.code == "missing_emoji" for i in result.issues)


def test_validator_rejects_emoji_only_in_title() -> None:
    body = (
        "Давление в салоне соответствует высоте около 2400 метров. "
        "Так устроены почти все пассажирские лайнеры для комфорта. "
    ) * 4
    result = validate_paragraph_draft(
        title="Дверь самолёта ✈️",
        teaser=body,
        body_html="История закончена нормально.",
        interaction_question="Знал?",
        button_options=["Да", "Нет"],
    )
    assert any(i.code == "missing_emoji" for i in result.issues)
