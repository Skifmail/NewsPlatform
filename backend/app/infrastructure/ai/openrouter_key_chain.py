"""Хранение и выбор API-ключей OpenRouter из настроек БД."""

from __future__ import annotations

from app.infrastructure.ai.openai_key_chain import (
    OpenAIKeyEntry as OpenRouterKeyEntry,
    active_openai_key as active_openrouter_key,
    mask_openai_keys_json as mask_openrouter_keys_json,
    merge_openai_keys_on_update as merge_openrouter_keys_on_update,
    parse_openai_keys as parse_openrouter_keys,
)

__all__ = [
    "OpenRouterKeyEntry",
    "active_openrouter_key",
    "mask_openrouter_keys_json",
    "merge_openrouter_keys_on_update",
    "parse_openrouter_keys",
]
