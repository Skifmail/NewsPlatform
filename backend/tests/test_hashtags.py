"""Тесты рубричных хэштегов для фильтрации ленты в мессенджерах."""

import json

from app.domain.article_meta import ArticleMeta, article_meta_from_dict
from app.domain.hashtags import (
    PARAGRAPH_HASHTAGS,
    build_pin_menu_text,
    format_hashtag_line,
    normalize_hashtag,
    parse_hashtag_list,
    resolve_post_hashtags,
)
from app.utils.text_format import append_hashtags, apply_channel_hashtags


def test_normalize_hashtag() -> None:
    assert normalize_hashtag("Авиация") == "#авиация"
    assert normalize_hashtag("#Физика,") == "#физика"
    assert normalize_hashtag("") == ""


def test_parse_hashtag_list() -> None:
    assert parse_hashtag_list("#авиация #физика") == ["#авиация", "#физика"]
    assert parse_hashtag_list("авиация, катастрофы\nкосмос") == [
        "#авиация",
        "#катастрофы",
        "#космос",
    ]


def test_resolve_prefers_meta_hashtags() -> None:
    meta = ArticleMeta(
        category="science",
        hashtags=["#авиация", "#физика", "#unknown"],
    )
    tags = resolve_post_hashtags(
        meta=meta,
        channel_hashtags="\n".join(PARAGRAPH_HASHTAGS),
        channel_name="Параграф",
    )
    assert tags == ["#авиация", "#физика"]


def test_resolve_fallback_from_category() -> None:
    meta = ArticleMeta(category="error")
    tags = resolve_post_hashtags(
        meta=meta,
        channel_name="Параграф TG",
    )
    assert tags == ["#катастрофы", "#технологии"]


def test_resolve_drops_disaster_tag_outside_error_category() -> None:
    """История/наука с #катастрофы от модели → fallback по category."""
    meta = ArticleMeta(category="history", hashtags=["#катастрофы"])
    tags = resolve_post_hashtags(
        meta=meta,
        channel_hashtags="\n".join(PARAGRAPH_HASHTAGS),
        channel_name="Параграф",
    )
    assert tags == ["#технологии", "#физика"]
    assert "#катастрофы" not in tags


def test_resolve_keeps_disaster_tag_for_error_category() -> None:
    meta = ArticleMeta(category="error", hashtags=["#катастрофы", "#авиация"])
    tags = resolve_post_hashtags(
        meta=meta,
        channel_hashtags="\n".join(PARAGRAPH_HASHTAGS),
        channel_name="Параграф",
    )
    assert tags == ["#катастрофы", "#авиация"]


def test_resolve_empty_without_catalog() -> None:
    tags = resolve_post_hashtags(
        meta=ArticleMeta(category="science", hashtags=["#физика"]),
        channel_name="Github находки",
    )
    assert tags == []


def test_append_hashtags() -> None:
    result = append_hashtags("<b>Текст</b>", ["#авиация", "#физика"])
    assert result.endswith("#авиация #физика")
    assert result.startswith("<b>Текст</b>")


def test_apply_channel_hashtags_from_meta_json() -> None:
    meta = article_meta_from_dict(
        {"category": "science", "hashtags": ["#космос", "#физика"]}
    )
    text = apply_channel_hashtags(
        "Тело поста",
        article_meta=json.dumps(meta.to_dict(), ensure_ascii=False),
        channel_hashtags="\n".join(PARAGRAPH_HASHTAGS),
        channel_name="Параграф",
    )
    assert "#космос #физика" in text


def test_pin_menu_contains_all_rubrics() -> None:
    menu = build_pin_menu_text()
    for tag in PARAGRAPH_HASHTAGS:
        assert tag in menu
    assert "Рубрики канала" in menu


def test_format_hashtag_line() -> None:
    assert format_hashtag_line(["#авиация", "#физика"]) == "#авиация #физика"
    assert format_hashtag_line([]) == ""
