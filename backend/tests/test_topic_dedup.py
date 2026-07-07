"""Тесты дедупликации тем статей."""

from app.domain.topic_dedup import is_topic_too_similar


def test_flamingo_rephrase_detected() -> None:
    recent = ["Фламинго: почему они розовые и от чего зависит цвет"]
    assert is_topic_too_similar("Биохимия розового окраса фламинго", recent)
    assert is_topic_too_similar("Розовый цвет фламинго — откуда берётся", recent)


def test_lithops_rephrase_detected() -> None:
    recent = ["Литопсы: живые камни пустыни"]
    assert is_topic_too_similar("Живые камни Lithops и их маскировка", recent)


def test_different_topics_allowed() -> None:
    recent = ["Фламинго: почему они розовые"]
    assert not is_topic_too_similar("Как муравьи строят мегаполисы", recent)


def test_placebo_synonym_still_blocked() -> None:
    recent = ["Эффект плацебо: сила ожидания"]
    assert is_topic_too_similar("Сахарная таблетка и самовнушение", recent)
