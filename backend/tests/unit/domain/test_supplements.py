"""Проверки правил дополнительных публикаций до реализации."""

from datetime import UTC, datetime

import pytest

from app.domain.supplements import (
    SupplementError,
    due_kind,
    validate_decision,
    validate_text,
)


@pytest.mark.parametrize(
    ("at", "expected"),
    [
        ("2026-09-14T14:59:00+00:00", None),
        ("2026-09-14T15:00:00+00:00", "fact"),
        ("2026-09-16T15:00:00+00:00", "news"),
        ("2026-09-18T15:00:00+00:00", "fact"),
        ("2026-09-15T15:00:00+00:00", None),
        ("2026-09-14T21:00:00+00:00", None),
    ],
)
def test_due_kind_when_schedule_boundary_should_select_local_day(
    at: str, expected: str | None
) -> None:
    """Проверяет расписание в московском часовом поясе."""
    assert due_kind(datetime.fromisoformat(at), "18:00", [0, 4], 2) == expected


@pytest.mark.parametrize("clock", ["25:00", "18:60", "9:00", "", "18:00:00"])
def test_due_kind_when_invalid_clock_should_raise(clock: str) -> None:
    """Отклоняет неоднозначное или некорректное время."""
    with pytest.raises(SupplementError):
        due_kind(datetime.now(UTC), clock, [0, 4], 2)


@pytest.mark.parametrize("text", ["", "Факт. Второй факт.", "<b>Факт</b>", "x" * 501])
def test_validate_text_when_fact_invalid_should_raise(text: str) -> None:
    """Не пропускает пустой, длинный и многофразовый факт."""
    with pytest.raises(SupplementError):
        validate_text(text, "fact")


def test_validate_text_when_decimal_should_keep_single_sentence() -> None:
    """Десятичная точка не разделяет предложения."""
    validate_text("Измеренное значение составило 3.14 единицы.", "fact")


def test_validate_text_when_fact_is_expert_level_should_raise() -> None:
    """Не пропускает отклонённую редактором перегруженную формулировку."""
    with pytest.raises(SupplementError, match="простыми словами"):
        validate_text(
            "Физики из Университета Карнеги-Меллона обнаружили аномальный эффект "
            "Холла в плоскости низкоразмерной системы, показав, что электрический "
            "отклик возникает и при параллельном магнитном поле, что меняет "
            "столетнее представление.",
            "fact",
        )


def test_validate_text_when_fact_is_plain_should_allow() -> None:
    """Пропускает один короткий факт с одной понятной мыслью."""
    validate_text(
        "Утконос находит добычу с закрытыми глазами, улавливая клювом слабые "
        "электрические сигналы её мышц.",
        "fact",
    )


@pytest.mark.parametrize(
    ("state", "user", "version", "message"),
    [
        ("published", 7, 2, "mid"),
        ("awaiting", 8, 2, "mid"),
        ("awaiting", 7, 1, "mid"),
        ("awaiting", 7, 2, "other"),
    ],
)
def test_validate_decision_when_unauthorized_or_stale_should_raise(
    state: str, user: int, version: int, message: str
) -> None:
    """Защищает от чужого аккаунта, старой версии и повторного нажатия."""
    with pytest.raises(SupplementError):
        validate_decision(state, user, 7, version, 2, message, "mid")


def test_validate_decision_when_matching_review_should_allow() -> None:
    """Разрешает только актуальную карточку владельца."""
    validate_decision("awaiting", 7, 7, 2, 2, "mid", "mid")


@pytest.mark.parametrize("days,news", [([0, 0], 2), ([0, 7], 2), ([0, 2], 2)])
def test_due_kind_when_conflicting_days_should_raise(
    days: list[int], news: int
) -> None:
    """Не разрешает неоднозначные и выходящие за неделю дни."""
    with pytest.raises(SupplementError):
        due_kind(datetime.now(UTC), "18:00", days, news)
