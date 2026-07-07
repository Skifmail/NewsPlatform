"""Тесты очистки body_html от служебных меток."""

from app.utils.article_body_sanitize import (
    dedupe_teaser_hook_from_body,
    sanitize_article_body_html,
    strip_article_structure_labels,
)


def test_strip_structure_labels_from_paragraph_body() -> None:
    body = (
        "<b>Литопсы: живые камни</b>\n\n"
        "Крючок\n"
        "🧠 Представьте: вы идёте по пустыне.\n\n"
        "<b>Что такое литопс</b>\n\n"
        "Текст раздела.\n\n"
        "Неожиданный поворот\n"
        "Литопсы меняют цвет.\n\n"
        "Вывод\n"
        "Литопсы — гениальные имитаторы."
    )
    cleaned = strip_article_structure_labels(body)
    assert "Крючок" not in cleaned
    assert "Неожиданный поворот" not in cleaned
    assert "Вывод" not in cleaned
    assert "Что такое литопс" in cleaned
    assert "🧠 Представьте" in cleaned
    assert "гениальные имитаторы" in cleaned


def test_dedupe_hook_from_body() -> None:
    teaser = (
        "<b>Литопсы: живые камни</b>\n\n"
        "🧠 Представьте: вы идёте по пустыне, смотрите под ноги."
    )
    body = (
        "🧠 Представьте: вы идёте по пустыне, смотрите под ноги.\n\n"
        "<b>Раздел</b>\n\n"
        "Основной текст."
    )
    result = dedupe_teaser_hook_from_body(body, teaser)
    assert "🧠 Представьте" not in result.split("Раздел")[0]
    assert "Основной текст" in result


def test_sanitize_full_pipeline() -> None:
    teaser = "<b>Title</b>\n\n🧠 Hook text about desert walk."
    body = (
        "Крючок\n\n"
        "🧠 Hook text about desert walk.\n\n"
        "<b>Section</b>\n\n"
        "Content.\n\n"
        "Вывод\n\n"
        "Final thoughts."
    )
    result = sanitize_article_body_html(body, teaser_html=teaser)
    assert "Крючок" not in result
    assert "Вывод" not in result
    assert "Hook text about desert walk" not in result
    assert "Content" in result
    assert "Final thoughts" in result
