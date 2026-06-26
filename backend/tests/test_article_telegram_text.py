"""Тесты сборки длинного текста статьи для Telegram."""

from app.utils.text_format import (
    TELEGRAM_USER_CAPTION_MAX,
    build_article_telegram_text,
)


def test_build_article_merges_teaser_and_body() -> None:
    text = build_article_telegram_text(
        article_title="Заголовок",
        teaser_html="<b>Карточка</b>\n\nКрючок",
        body_html="<b>Раздел</b>\n\nОсновной текст статьи.",
    )
    assert "<b>Карточка</b>" in text
    assert "Основной текст статьи" in text
    assert "Заголовок" not in text or "Карточка" in text


def test_build_article_uses_title_when_no_teaser() -> None:
    text = build_article_telegram_text(
        article_title="Только заголовок",
        teaser_html="",
        body_html="Тело поста.",
    )
    assert "<b>Только заголовок</b>" in text
    assert "Тело поста" in text


def test_build_article_truncates_to_user_caption_max() -> None:
    body = "а" * 5000
    text = build_article_telegram_text(
        article_title=None,
        teaser_html="<b>X</b>",
        body_html=body,
        max_length=TELEGRAM_USER_CAPTION_MAX,
    )
    assert len(text) <= TELEGRAM_USER_CAPTION_MAX
    assert len(text) >= TELEGRAM_USER_CAPTION_MAX - 50
