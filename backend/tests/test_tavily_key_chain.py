"""Тесты цепочки ключей Tavily."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.infrastructure.search.tavily_key_chain import (
    TavilyKeyEntry,
    is_masked_api_key,
    is_quota_exhausted,
    mask_api_key,
    merge_keys_on_update,
    ordered_keys_for_use,
    parse_stored_keys,
    resolve_keys,
)


def test_mask_and_detect_masked_key() -> None:
    masked = mask_api_key("tvly-abcdefghijklmnop")
    assert is_masked_api_key(masked)
    assert masked.startswith("tvly")
    assert masked.endswith("mnop")


def test_merge_keys_preserves_secret_for_masked() -> None:
    previous = '[{"id":"a1","label":"Основной","key":"tvly-secret-key-1111"}]'
    incoming = (
        '[{"id":"a1","label":"Основной","key":"'
        + mask_api_key("tvly-secret-key-1111")
        + '"},'
        '{"id":"b2","label":"Запасной","key":"tvly-new-key-2222"}]'
    )
    merged = merge_keys_on_update(previous_raw=previous, incoming_raw=incoming)
    entries = parse_stored_keys(merged)
    assert len(entries) == 2
    by_id = {item.id: item for item in entries}
    assert by_id["a1"].key == "tvly-secret-key-1111"
    assert by_id["b2"].key == "tvly-new-key-2222"


def test_resolve_keys_includes_env() -> None:
    with patch(
        "app.infrastructure.search.tavily_key_chain.get_settings"
    ) as settings_mock:
        settings_mock.return_value = MagicMock(tavily_api_key="tvly-env-key-9999")
        keys = resolve_keys(
            '[{"id":"db1","label":"DB","key":"tvly-db-key-8888"}]'
        )
    assert keys[0].id == "env"
    assert keys[0].source == "env"
    assert keys[1].id == "db1"


def test_ordered_keys_skips_exhausted() -> None:
    keys = [
        TavilyKeyEntry(id="a", label="A", key="k1", source="db"),
        TavilyKeyEntry(id="b", label="B", key="k2", source="db"),
    ]
    with patch(
        "app.infrastructure.search.tavily_key_chain.is_key_exhausted",
        side_effect=lambda key_id: key_id == "a",
    ):
        ordered = ordered_keys_for_use(
            keys, active_key_id="a", auto_switch=True
        )
    assert [item.id for item in ordered] == ["b"]


def test_ordered_keys_without_auto_switch_only_active() -> None:
    keys = [
        TavilyKeyEntry(id="a", label="A", key="k1", source="db"),
        TavilyKeyEntry(id="b", label="B", key="k2", source="db"),
    ]
    with patch(
        "app.infrastructure.search.tavily_key_chain.is_key_exhausted",
        return_value=False,
    ):
        ordered = ordered_keys_for_use(
            keys, active_key_id="b", auto_switch=False
        )
    assert [item.id for item in ordered] == ["b"]


def test_is_quota_exhausted_detects_credits() -> None:
    assert is_quota_exhausted(status_code=402, body_text="") is True
    assert (
        is_quota_exhausted(
            status_code=429,
            body_text='{"detail":"Insufficient credits"}',
        )
        is True
    )
    assert is_quota_exhausted(status_code=429, body_text="rate limit") is False
