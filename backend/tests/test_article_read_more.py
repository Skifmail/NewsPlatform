"""Тесты CTA-ссылки на полную статью (Telegraph)."""

from app.utils.text_format import (
    build_article_read_more_html,
    pick_article_read_more_label,
)


def test_pick_install_label_from_body_hints() -> None:
    label = pick_article_read_more_label(
        channel_name="ПАРАГРАФ (МАКС)",
        article_title="Restic",
        article_body="<b>Установка</b>\n\nbrew install restic",
    )
    assert label == "Как установить →"


def test_pick_use_label_from_body_hints() -> None:
    label = pick_article_read_more_label(
        channel_name="Блог",
        article_title="HTTPie",
        article_body="Примеры использования API и команд",
    )
    assert label == "Как использовать →"


def test_pick_rotates_labels_for_paragraph_channel() -> None:
    first = pick_article_read_more_label(
        channel_name="ПАРАГРАФ (МАКС)",
        article_title="Тема",
        article_body="Обзор",
        post_id=1,
    )
    second = pick_article_read_more_label(
        channel_name="ПАРАГРАФ (МАКС)",
        article_title="Тема",
        article_body="Обзор",
        post_id=2,
    )
    assert first != second
    assert first.endswith("→")
    assert second.endswith("→")


def test_build_article_read_more_html_is_button_like() -> None:
    html = build_article_read_more_html(
        "https://telegra.ph/Test-06-24",
        channel_name="ПАРАГРАФ (МАКС)",
        article_title="Тема",
        article_body="brew install tool",
        post_id=7,
    )
    assert "https://telegra.ph/Test-06-24" in html
    assert "<b>" in html
    assert "<u>" in html
    assert "👉" in html
    assert "Как установить →" in html
    assert "Читать полностью" not in html
