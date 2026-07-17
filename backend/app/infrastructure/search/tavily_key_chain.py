"""Цепочка API-ключей Tavily: выбор активного и автопереключение при лимите."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import redis
from loguru import logger

from app.core.config import get_settings

_EXHAUSTED_PREFIX = "tavily:exhausted:"
_ENV_KEY_ID = "env"
_MASK_MARKER = "…"
_PLACEHOLDERS = frozenset({"", "tvly-...", "tvly-…", "your_api_key", "change_me"})

_QUOTA_MARKERS = (
    "insufficient credits",
    "out of credits",
    "credit limit",
    "credits exhausted",
    "no credits",
    "usage limit",
    "plan limit",
    "monthly limit",
    "quota exceeded",
    "quota exhausted",
    "payment required",
)


@dataclass(frozen=True)
class TavilyKeyEntry:
    """Один API-ключ Tavily в цепочке.

    Attributes:
        id: стабильный идентификатор (env или UUID).
        label: подпись для панели настроек.
        key: секретный API-ключ.
        source: env | db.
    """

    id: str
    label: str
    key: str
    source: str


def is_key_configured(key: str) -> bool:
    """Проверяет, что строка похожа на реальный ключ, а не плейсхолдер.

    Args:
        key: значение API-ключа.

    Returns:
        bool: True если ключ задан.
    """
    normalized = key.strip().lower()
    return bool(normalized) and normalized not in _PLACEHOLDERS


def mask_api_key(key: str) -> str:
    """Маскирует ключ для ответа API (последние 4 символа).

    Args:
        key: полный API-ключ.

    Returns:
        str: маскированная строка.
    """
    raw = key.strip()
    if len(raw) <= 4:
        return f"{_MASK_MARKER}{raw}"
    return f"{raw[:4]}{_MASK_MARKER}{raw[-4:]}"


def is_masked_api_key(key: str) -> bool:
    """Определяет, что значение — маска, а не новый секрет.

    Args:
        key: строка из PATCH настроек.

    Returns:
        bool: True если ключ замаскирован.
    """
    return _MASK_MARKER in key or "***" in key or "••" in key


def key_fingerprint(key: str) -> str:
    """Короткий отпечаток ключа для логов (без секрета).

    Args:
        key: API-ключ.

    Returns:
        str: 8 hex-символов SHA-256.
    """
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:8]


def parse_stored_keys(raw: str | None) -> list[TavilyKeyEntry]:
    """Разбирает JSON-список ключей из настроек БД.

    Args:
        raw: JSON-массив объектов id/label/key.

    Returns:
        list[TavilyKeyEntry]: ключи из БД.
    """
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Invalid tavily_api_keys JSON")
        return []
    if not isinstance(data, list):
        return []

    result: list[TavilyKeyEntry] = []
    seen_ids: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if not is_key_configured(key):
            continue
        key_id = str(item.get("id") or "").strip() or str(uuid.uuid4())
        if key_id == _ENV_KEY_ID or key_id in seen_ids:
            key_id = str(uuid.uuid4())
        seen_ids.add(key_id)
        label = str(item.get("label") or "").strip() or f"Ключ {len(result) + 1}"
        result.append(
            TavilyKeyEntry(id=key_id, label=label, key=key, source="db")
        )
    return result


def resolve_keys(raw_db: str | None = None) -> list[TavilyKeyEntry]:
    """Собирает цепочку ключей: .env + записи из БД.

    Args:
        raw_db: JSON из настройки tavily_api_keys.

    Returns:
        list[TavilyKeyEntry]: уникальные ключи в порядке приоритета.
    """
    settings = get_settings()
    result: list[TavilyKeyEntry] = []
    seen_secrets: set[str] = set()

    env_key = settings.tavily_api_key.strip()
    if is_key_configured(env_key):
        result.append(
            TavilyKeyEntry(
                id=_ENV_KEY_ID,
                label="Из .env",
                key=env_key,
                source="env",
            )
        )
        seen_secrets.add(env_key)

    for entry in parse_stored_keys(raw_db):
        if entry.key in seen_secrets:
            continue
        seen_secrets.add(entry.key)
        result.append(entry)
    return result


def serialize_stored_keys(entries: list[TavilyKeyEntry]) -> str:
    """Сериализует только ключи из БД (без env) для сохранения.

    Args:
        entries: полная или частичная цепочка.

    Returns:
        str: JSON для settings.tavily_api_keys.
    """
    payload = [
        {"id": item.id, "label": item.label, "key": item.key}
        for item in entries
        if item.source == "db"
    ]
    return json.dumps(payload, ensure_ascii=False)


def merge_keys_on_update(
    *,
    previous_raw: str | None,
    incoming_raw: str | None,
) -> str:
    """Сливает PATCH ключей: маскированные значения сохраняют старый секрет.

    Args:
        previous_raw: текущий JSON в БД.
        incoming_raw: новый JSON из панели (ключи могут быть замаскированы).

    Returns:
        str: JSON для записи в БД.
    """
    previous = {item.id: item for item in parse_stored_keys(previous_raw)}
    if incoming_raw is None:
        return serialize_stored_keys(list(previous.values()))

    try:
        data = json.loads(incoming_raw) if incoming_raw.strip() else []
    except json.JSONDecodeError as exc:
        msg = "Некорректный JSON tavily_api_keys"
        raise ValueError(msg) from exc
    if not isinstance(data, list):
        msg = "tavily_api_keys должен быть JSON-массивом"
        raise ValueError(msg)

    merged: list[TavilyKeyEntry] = []
    seen_ids: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            continue
        key_id = str(item.get("id") or "").strip()
        if key_id == _ENV_KEY_ID:
            continue
        if not key_id:
            key_id = str(uuid.uuid4())
        if key_id in seen_ids:
            continue
        seen_ids.add(key_id)

        label = str(item.get("label") or "").strip() or f"Ключ {len(merged) + 1}"
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
            TavilyKeyEntry(id=key_id, label=label, key=secret, source="db")
        )
    return serialize_stored_keys(merged)


def mask_keys_json(raw: str | None) -> str:
    """Маскирует секреты в JSON ключей для ответа GET /settings.

    Args:
        raw: JSON из БД.

    Returns:
        str: JSON с замаскированными ключами.
    """
    entries = parse_stored_keys(raw)
    payload = [
        {"id": item.id, "label": item.label, "key": mask_api_key(item.key)}
        for item in entries
    ]
    return json.dumps(payload, ensure_ascii=False)


def ordered_keys_for_use(
    keys: list[TavilyKeyEntry],
    *,
    active_key_id: str | None,
    auto_switch: bool,
) -> list[TavilyKeyEntry]:
    """Упорядочивает ключи: активный первым, исчерпанные пропускаются.

    Args:
        keys: полная цепочка.
        active_key_id: выбранный вручную id (или пусто).
        auto_switch: переключаться на следующий при исчерпании.

    Returns:
        list[TavilyKeyEntry]: ключи для попыток поиска.
    """
    if not keys:
        return []

    preferred_id = (active_key_id or "").strip()
    ordered: list[TavilyKeyEntry] = []
    if preferred_id:
        for item in keys:
            if item.id == preferred_id:
                ordered.append(item)
                break
    for item in keys:
        if item.id == preferred_id:
            continue
        ordered.append(item)

    if not auto_switch:
        return ordered[:1]

    available = [item for item in ordered if not is_key_exhausted(item.id)]
    return available if available else []


def parse_bool_setting(raw: str | None, default: bool = True) -> bool:
    """Парсит булеву настройку из строки БД.

    Args:
        raw: значение настройки.
        default: значение по умолчанию.

    Returns:
        bool: результат.
    """
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"true", "1", "yes", "on"}


def is_quota_exhausted(*, status_code: int, body_text: str = "") -> bool:
    """Проверяет, что ошибка Tavily связана с исчерпанием кредитов.

    Args:
        status_code: HTTP-код ответа.
        body_text: тело ответа.

    Returns:
        bool: True если нужно переключить ключ.
    """
    if status_code == 402:
        return True
    combined = body_text.lower()
    if any(marker in combined for marker in _QUOTA_MARKERS):
        return True
    if status_code in {403, 429} and "credit" in combined:
        return True
    return False


def exhausted_ttl_seconds() -> int:
    """TTL пометки исчерпания — до начала следующего месяца UTC.

    Returns:
        int: секунды до сброса месячного лимита Tavily.
    """
    now = datetime.now(UTC)
    if now.month == 12:
        nxt = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        nxt = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return max(int((nxt - now).total_seconds()), 3600)


def _redis_client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url)


def mark_key_exhausted(key_id: str) -> None:
    """Помечает ключ исчерпанным до конца биллинг-месяца.

    Args:
        key_id: идентификатор ключа в цепочке.
    """
    ttl = exhausted_ttl_seconds()
    try:
        _redis_client().setex(f"{_EXHAUSTED_PREFIX}{key_id}", ttl, "1")
        logger.warning(
            "Tavily key marked exhausted",
            key_id=key_id,
            retry_after_hours=ttl // 3600,
        )
    except Exception as exc:
        logger.warning(
            "Failed to mark Tavily key exhausted",
            key_id=key_id,
            error=str(exc),
        )


def clear_key_exhausted(key_id: str) -> None:
    """Снимает пометку исчерпания (после ручного выбора или пополнения).

    Args:
        key_id: идентификатор ключа.
    """
    try:
        _redis_client().delete(f"{_EXHAUSTED_PREFIX}{key_id}")
    except Exception as exc:
        logger.warning(
            "Failed to clear Tavily exhausted flag",
            key_id=key_id,
            error=str(exc),
        )


def is_key_exhausted(key_id: str) -> bool:
    """Проверяет, помечен ли ключ исчерпанным в Redis.

    Args:
        key_id: идентификатор ключа.

    Returns:
        bool: True если ключ временно пропущен.
    """
    try:
        return bool(_redis_client().get(f"{_EXHAUSTED_PREFIX}{key_id}"))
    except Exception:
        return False


def list_exhausted_keys() -> list[dict[str, int | str]]:
    """Список исчерпанных ключей с TTL.

    Returns:
        list[dict]: key_id, ttl_seconds.
    """
    try:
        client = _redis_client()
        result: list[dict[str, int | str]] = []
        for key in client.scan_iter(f"{_EXHAUSTED_PREFIX}*"):
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            key_id = key_str.removeprefix(_EXHAUSTED_PREFIX)
            ttl = int(client.ttl(key_str))
            if ttl > 0:
                result.append({"key_id": key_id, "ttl_seconds": ttl})
        return sorted(result, key=lambda item: str(item["key_id"]))
    except Exception as exc:
        logger.warning("Failed to list exhausted Tavily keys", error=str(exc))
        return []


def new_key_id() -> str:
    """Генерирует id для нового ключа в БД.

    Returns:
        str: UUID4.
    """
    return str(uuid.uuid4())


_LABEL_SAFE = re.compile(r"[^\w\s\-.—()]+", re.UNICODE)


def sanitize_label(label: str, fallback: str) -> str:
    """Нормализует подпись ключа.

    Args:
        label: введённая подпись.
        fallback: запасное имя.

    Returns:
        str: очищенная подпись.
    """
    cleaned = _LABEL_SAFE.sub("", label).strip()
    return cleaned[:80] or fallback
