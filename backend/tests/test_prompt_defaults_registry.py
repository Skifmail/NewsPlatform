"""Тесты целостности реестра промптов.

Ловят рассинхрон между кодом и БД-реестром на CI, а не в рантайме
падением Celery-задачи: опечатка в ключе, необъявленная переменная
шаблона, поле длиннее колонки.
"""

import re
from pathlib import Path

import pytest

from app.domain.prompt_defaults import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    PROMPT_DEFAULTS,
)
from app.utils.safe_format import safe_format

APP_DIR = Path(__file__).resolve().parent.parent / "app"

# Ключи, запрашиваемые из кода через PromptService.get("...").
_REQUESTED_KEY_RE = re.compile(r'_prompts\.get\(\s*"([a-z_.]+)"')

# Плейсхолдер {var}, но не литеральная пара {{...}} из JSON-примеров.
_PLACEHOLDER_RE = re.compile(r"(?<!\{)\{([a-z_]+)\}(?!\})")


def _requested_keys() -> dict[str, set[str]]:
    """Ключи промптов, запрашиваемые кодом → файлы, где они встречаются."""
    found: dict[str, set[str]] = {}
    for path in APP_DIR.rglob("*.py"):
        for key in _REQUESTED_KEY_RE.findall(path.read_text(encoding="utf-8")):
            found.setdefault(key, set()).add(path.name)
    return found


def test_every_requested_key_exists_in_defaults() -> None:
    """Код не запрашивает промптов, которых нет в реестре."""
    requested = _requested_keys()
    assert requested, "не найдено ни одного вызова PromptService.get — проверь regex"

    missing = {k: sorted(v) for k, v in requested.items() if k not in PROMPT_DEFAULTS}
    assert not missing, f"ключи запрашиваются, но отсутствуют в дефолтах: {missing}"


def test_prompt_keys_are_unique() -> None:
    for key, entry in PROMPT_DEFAULTS.items():
        assert key == entry.key, f"ключ словаря {key} не совпадает с entry.key {entry.key}"


@pytest.mark.parametrize("key", sorted(PROMPT_DEFAULTS))
def test_declared_variables_match_template(key: str) -> None:
    """template_variables точно перечисляет плейсхолдеры шаблона."""
    entry = PROMPT_DEFAULTS[key]
    in_text = set(_PLACEHOLDER_RE.findall(entry.template_text))
    declared = set(entry.template_variables)
    assert in_text == declared, (
        f"{key}: в тексте {sorted(in_text)}, объявлено {sorted(declared)}"
    )


@pytest.mark.parametrize("key", sorted(PROMPT_DEFAULTS))
def test_template_renders_all_variables(key: str) -> None:
    """После safe_format в тексте не остаётся неподставленных плейсхолдеров."""
    entry = PROMPT_DEFAULTS[key]
    rendered = safe_format(
        entry.template_text, **{v: f"<{v}>" for v in entry.template_variables}
    )
    for var in entry.template_variables:
        assert f"{{{var}}}" not in rendered, f"{key}: {{{var}}} не подставилась"


@pytest.mark.parametrize("key", sorted(PROMPT_DEFAULTS))
def test_entry_fits_column_limits(key: str) -> None:
    """Поля влезают в ограничения колонок prompt_templates."""
    entry = PROMPT_DEFAULTS[key]
    assert len(entry.key) <= 120
    assert len(entry.name) <= 200
    assert len(entry.category) <= 40
    assert len(entry.channel_scope) <= 60
    assert entry.template_text.strip(), "текст промпта пуст"
    assert entry.description.strip(), "описание промпта пусто"


def test_categories_are_declared() -> None:
    """Каждая категория из записей описана в CATEGORY_ORDER и CATEGORY_LABELS."""
    used = {entry.category for entry in PROMPT_DEFAULTS.values()}
    assert used == set(CATEGORY_ORDER), (
        f"категории записей {sorted(used)} != CATEGORY_ORDER {sorted(CATEGORY_ORDER)}"
    )
    assert used == set(CATEGORY_LABELS), "не у всех категорий есть русское название"
