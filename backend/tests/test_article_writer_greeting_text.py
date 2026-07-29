"""Тест: ArticleWriter извлекает greeting_text для открыток (с мягким фолбэком)."""

from types import SimpleNamespace

from app.infrastructure.ai.article_writer import ArticleWriter


def _postcard_channel() -> SimpleNamespace:
    return SimpleNamespace(name="Открытки от души", topic="postcard")


def test_extracts_greeting_text_from_model_response() -> None:
    raw = (
        '{"title": "День рождения", "teaser": "С днём рождения! \\ud83c\\udf89", '
        '"body_html": "Пусть каждый день радует", "greeting_text": "С Днём Рождения!", '
        '"image_prompt": "confetti and golden lights"}'
    )
    draft = ArticleWriter._parse_response(
        raw, body_max_length=150, teaser_max_length=200, channel=_postcard_channel()
    )
    assert draft is not None
    assert draft.greeting_text == "С Днём Рождения!"


def test_falls_back_to_title_when_greeting_text_missing() -> None:
    raw = (
        '{"title": "Доброе утро", "teaser": "Доброе утро! Пусть день будет светлым \\u2600", '
        '"body_html": "Хорошего дня", "image_prompt": "sunrise breakfast window"}'
    )
    draft = ArticleWriter._parse_response(
        raw, body_max_length=150, teaser_max_length=200, channel=_postcard_channel()
    )
    assert draft is not None
    assert draft.greeting_text == "Доброе утро"
