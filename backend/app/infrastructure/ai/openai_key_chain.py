"""Хранение и выбор API-ключей OpenAI из настроек БД."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass

from loguru import logger

from app.infrastructure.search.tavily_key_chain import (
    is_key_configured,
    is_masked_api_key,
    mask_api_key,
)


@dataclass(frozen=True)
class OpenAIKeyEntry:
    id: str
    label: str
    note: str
    key: str
    enabled: bool


def parse_openai_keys(raw: str | None) -> list[OpenAIKeyEntry]:
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid openai_api_keys JSON")
        return []
    if not isinstance(data, list):
        return []

    result: list[OpenAIKeyEntry] = []
    seen_ids: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not is_key_configured(key):
            continue
        key_id = str(item.get("id") or "").strip() or str(uuid.uuid4())
        if key_id in seen_ids:
            key_id = str(uuid.uuid4())
        seen_ids.add(key_id)
        label = str(item.get("label") or "").strip() or f"Ключ {len(result) + 1}"
        note = str(item.get("note") or "").strip()
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            enabled = str(enabled).lower() in {"true", "1", "yes", "on"}
        result.append(
            OpenAIKeyEntry(
                id=key_id, label=label, note=note, key=key, enabled=enabled,
            )
        )
    return result


def active_openai_key(raw: str | None) -> str | None:
    for entry in parse_openai_keys(raw):
        if entry.enabled:
            return entry.key
    return None


def mask_openai_keys_json(raw: str | None) -> str:
    entries = parse_openai_keys(raw)
    payload = [
        {
            "id": e.id,
            "label": e.label,
            "note": e.note,
            "key": mask_api_key(e.key),
            "enabled": e.enabled,
        }
        for e in entries
    ]
    return json.dumps(payload, ensure_ascii=False)


def merge_openai_keys_on_update(
    *,
    previous_raw: str | None,
    incoming_raw: str | None,
) -> str:
    previous = {e.id: e for e in parse_openai_keys(previous_raw)}

    if incoming_raw is None:
        return _serialize(list(previous.values()))

    try:
        data = json.loads(incoming_raw) if incoming_raw.strip() else []
    except json.JSONDecodeError as exc:
        msg = "Некорректный JSON openai_api_keys"
        raise ValueError(msg) from exc
    if not isinstance(data, list):
        msg = "openai_api_keys должен быть JSON-массивом"
        raise ValueError(msg)

    merged: list[OpenAIKeyEntry] = []
    seen_ids: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        key_id = str(item.get("id") or "").strip()
        if not key_id:
            key_id = str(uuid.uuid4())
        if key_id in seen_ids:
            continue
        seen_ids.add(key_id)

        label = str(item.get("label") or "").strip() or f"Ключ {len(merged) + 1}"
        note = str(item.get("note") or "").strip()
        enabled = item.get("enabled", True)
        if not isinstance(enabled, bool):
            enabled = str(enabled).lower() in {"true", "1", "yes", "on"}

        raw_key = str(item.get("key") or "").strip()
        if is_masked_api_key(raw_key):
            old = previous.get(key_id)
            if old is None:
                continue
            secret = old.key
        else:
            if not is_key_configured(raw_key):
                continue
            secret = raw_key

        merged.append(
            OpenAIKeyEntry(
                id=key_id, label=label, note=note, key=secret, enabled=enabled,
            )
        )
    return _serialize(merged)


def _serialize(entries: list[OpenAIKeyEntry]) -> str:
    payload = [
        {
            "id": e.id,
            "label": e.label,
            "note": e.note,
            "key": e.key,
            "enabled": e.enabled,
        }
        for e in entries
    ]
    return json.dumps(payload, ensure_ascii=False)
