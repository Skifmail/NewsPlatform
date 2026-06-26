"""Тесты ссылки перелива аудитории в конце поста."""

from app.utils.text_format import (
    MAX_MESSAGE_MAX,
    TELEGRAM_USER_CAPTION_MAX,
    append_cross_promote_footer,
    build_article_telegram_text,
    build_cross_promote_link_label,
    cross_promote_footer_length,
    long_form_body_limit,
)


def test_append_cross_promote_footer_adds_link() -> None:
    text = "<b>Заголовок</b>\n\nТекст поста"
    result = append_cross_promote_footer(
        text,
        "https://max.ru/paragraph",
        "Подписывайтесь на ПАРАГРАФ в MAX →",
    )
    assert "https://max.ru/paragraph" in result
    assert "Подписывайтесь на ПАРАГРАФ в MAX →" in result
    assert result.startswith("<b>Заголовок</b>")


def test_append_cross_promote_footer_skips_without_url() -> None:
    text = "Пост без ссылки"
    assert append_cross_promote_footer(text, None, "label") == text


def test_append_cross_promote_footer_no_duplicate() -> None:
    text = '<a href="https://max.ru/paragraph">Уже есть</a>'
    result = append_cross_promote_footer(
        text,
        "https://max.ru/paragraph",
        "Подписывайтесь в MAX →",
    )
    assert result == text


def test_build_cross_promote_link_label_with_emoji() -> None:
    label = build_cross_promote_link_label(
        "ПАРАГРАФ в MAX →",
        "5368324170671202286",
    )
    assert '<tg-emoji emoji-id="5368324170671202286">' in label
    assert "ПАРАГРАФ в MAX →" in label


def test_append_cross_promote_footer_with_custom_emoji() -> None:
    result = append_cross_promote_footer(
        "Текст",
        "https://max.ru/paragraph",
        "ПАРАГРАФ в MAX →",
        promote_emoji_id="5368324170671202286",
    )
    assert "tg-emoji" in result
    assert "https://max.ru/paragraph" in result


def test_cross_promote_footer_length_zero_without_url() -> None:
    assert cross_promote_footer_length(None) == 0
    assert cross_promote_footer_length("") == 0


def test_long_form_body_limit_reserves_teaser_and_footer() -> None:
    tg = long_form_body_limit(platform="telegram", teaser_max_length=900)
    mx = long_form_body_limit(platform="max", teaser_max_length=900)
    assert tg < TELEGRAM_USER_CAPTION_MAX - 900
    assert mx < MAX_MESSAGE_MAX - 900
    assert mx < tg  # у MAX лимит сообщения меньше


def test_long_form_full_post_fits_caption_limit() -> None:
    """Анонс + тело (по бюджету) + футер не превышают лимит сообщения."""
    teaser_max = 900
    body_budget = long_form_body_limit(platform="telegram", teaser_max_length=teaser_max)
    teaser = "<b>" + "Анонс " * 150  # ~ длинный анонс
    body = "Тело статьи. " * 400 + "<b>Источники</b> <a href=\"https://x.ru\">x</a>"
    footer_reserve = cross_promote_footer_length(
        "https://max.ru/paragraph", "ПАРАГРАФ в MAX →"
    )
    text = build_article_telegram_text(
        article_title="Заголовок",
        teaser_html=teaser[: teaser_max],
        body_html=body[:body_budget],
        max_length=TELEGRAM_USER_CAPTION_MAX - footer_reserve,
    )
    full = append_cross_promote_footer(
        text, "https://max.ru/paragraph", "ПАРАГРАФ в MAX →"
    )
    assert len(full) <= TELEGRAM_USER_CAPTION_MAX
    assert "https://max.ru/paragraph" in full
