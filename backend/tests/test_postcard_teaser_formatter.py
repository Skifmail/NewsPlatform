"""Тесты формата короткой открытки-поздравления."""

from app.domain.prompt_defaults import PROMPT_DEFAULTS
from app.infrastructure.ai.postcard_teaser_formatter import (
    is_postcard_article_channel,
)


def test_is_postcard_article_channel() -> None:
    assert is_postcard_article_channel("Открытки от души | На любой случай")
    assert not is_postcard_article_channel("ПАРАГРАФ")


def test_postcard_writing_default_mentions_teaser_limit() -> None:
    template = PROMPT_DEFAULTS["writing.postcard"].template_text
    assert "{teaser_max_length}" in template
    assert "teaser" in template
    assert "body_html" in template
