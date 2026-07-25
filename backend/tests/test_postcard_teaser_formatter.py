"""Тесты формата короткой открытки-поздравления."""

from app.infrastructure.ai.postcard_teaser_formatter import (
    is_postcard_article_channel,
    postcard_writing_instructions,
)


def test_is_postcard_article_channel() -> None:
    assert is_postcard_article_channel("Открытки от души | На любой случай")
    assert not is_postcard_article_channel("ПАРАГРАФ")


def test_postcard_writing_instructions_mentions_teaser_limit() -> None:
    text = postcard_writing_instructions(600)
    assert "600" in text
    assert "teaser" in text
    assert "body_html" in text
