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
from app.infrastructure.ai.paragraph_teaser_formatter import build_paragraph_teaser
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
        title="Факт",
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
