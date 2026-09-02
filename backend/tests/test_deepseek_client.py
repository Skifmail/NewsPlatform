"""Тесты разбора ответа DeepSeek API."""

import pytest

from app.infrastructure.ai.deepseek_client import _first_choice


def test_first_choice_returns_dict() -> None:
    data = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]}
    assert _first_choice(data)["finish_reason"] == "stop"


def test_first_choice_rejects_null_element() -> None:
    with pytest.raises(RuntimeError, match="некорректный элемент"):
        _first_choice({"choices": [None]})


def test_first_choice_rejects_empty_choices() -> None:
    with pytest.raises(RuntimeError, match="пустой ответ"):
        _first_choice({"choices": []})
