"""Цепочка моделей Qwen-Image и кэш исчерпанных квот."""

from __future__ import annotations

import json
import re

import redis
from loguru import logger

from app.core.config import get_settings

DEFAULT_GENERATE_MODELS: tuple[str, ...] = (
    "wan2.7-image-pro",
    "wan2.7-image",
    "qwen-image-2.0-pro",
    "qwen-image-2.0",
    "z-image-turbo",
)

DEFAULT_EDIT_MODELS: tuple[str, ...] = (
    "wan2.7-image-pro",
    "wan2.7-image",
    "qwen-image-edit-plus",
    "qwen-image-edit-max",
    "qwen-image-edit",
)

_EXHAUSTED_PREFIX = "qwen_image:exhausted:"
_EXHAUSTED_TTL_SECONDS = 6 * 3600

_QUOTA_MARKERS = (
    "allocationquota",
    "freetier",
    "free tier",
    "free quota",
    "quota exceeded",
    "insufficient quota",
    "out of quota",
    "no free quota",
    "exceeded your current quota",
)


def parse_model_chain(raw: str | None, *, fallback: tuple[str, ...]) -> list[str]:
    """Разбирает список моделей из строки (запятые или переносы строк).

    Args:
        raw: значение из .env или настроек панели.
        fallback: цепочка по умолчанию.

    Returns:
        list[str]: уникальные имена моделей в порядке приоритета.
    """
    if not raw or not str(raw).strip():
        return list(fallback)
    parts = re.split(r"[,;\n]+", str(raw))
    models: list[str] = []
    seen: set[str] = set()
    for part in parts:
        name = part.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        models.append(name)
    return models or list(fallback)


def resolve_generate_models(raw: str | None = None) -> list[str]:
    """Цепочка text-to-image моделей."""
    settings = get_settings()
    source = raw if raw is not None else settings.qwen_image_models
    fallback: tuple[str, ...]
    single = settings.qwen_image_model.strip()
    if single:
        rest = tuple(m for m in DEFAULT_GENERATE_MODELS if m != single)
        fallback = (single, *rest)
    else:
        fallback = DEFAULT_GENERATE_MODELS
    return parse_model_chain(source, fallback=fallback)


def resolve_edit_models(raw: str | None = None) -> list[str]:
    """Цепочка image-edit моделей."""
    settings = get_settings()
    source = raw if raw is not None else settings.qwen_image_edit_models
    return parse_model_chain(source, fallback=DEFAULT_EDIT_MODELS)


def sizes_for_model(model: str, default_size: str) -> list[str]:
    """Возвращает размеры для повтора при ошибке валидации."""
    if model.startswith("wan2.7-image"):
        return [default_size, "1664*928"]
    if model.startswith(("qwen-image-plus", "qwen-image-max")) or model == "qwen-image":
        return ["1664*928", default_size]
    return [default_size, "1664*928"]


def is_quota_exhausted(
    *,
    status_code: int,
    body_text: str = "",
    api_code: str | None = None,
    message: str | None = None,
) -> bool:
    """Проверяет, что ошибка связана с исчерпанием бесплатной квоты."""
    if status_code == 403:
        return True
    combined = f"{api_code or ''} {message or ''} {body_text}".lower()
    return any(marker in combined for marker in _QUOTA_MARKERS)


def is_invalid_size_error(
    *,
    body_text: str = "",
    api_code: str | None = None,
    message: str | None = None,
) -> bool:
    """Проверяет ошибку несовместимого размера изображения."""
    combined = f"{api_code or ''} {message or ''} {body_text}".lower()
    return "size" in combined or "resolution" in combined or "pixel" in combined


def _redis_client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url)


def mark_model_exhausted(model: str) -> None:
    """Помечает модель как временно недоступную по квоте."""
    try:
        _redis_client().setex(f"{_EXHAUSTED_PREFIX}{model}", _EXHAUSTED_TTL_SECONDS, "1")
        logger.warning(
            "Qwen image model marked exhausted",
            model=model,
            retry_after_hours=_EXHAUSTED_TTL_SECONDS // 3600,
        )
    except Exception as exc:
        logger.warning("Failed to mark exhausted model", model=model, error=str(exc))


def is_model_exhausted(model: str) -> bool:
    """Проверяет, помечена ли модель исчерпанной в Redis."""
    try:
        return bool(_redis_client().get(f"{_EXHAUSTED_PREFIX}{model}"))
    except Exception:
        return False


def list_exhausted_models() -> list[dict[str, int | str]]:
    """Список моделей с исчерпанной квотой и TTL (секунды).

    Returns:
        list[dict]: model, ttl_seconds.
    """
    try:
        client = _redis_client()
        result: list[dict[str, int | str]] = []
        for key in client.scan_iter(f"{_EXHAUSTED_PREFIX}*"):
            key_str = key.decode() if isinstance(key, bytes) else str(key)
            model = key_str.removeprefix(_EXHAUSTED_PREFIX)
            ttl = int(client.ttl(key_str))
            if ttl > 0:
                result.append({"model": model, "ttl_seconds": ttl})
        return sorted(result, key=lambda item: str(item["model"]))
    except Exception as exc:
        logger.warning("Failed to list exhausted models", error=str(exc))
        return []


def exhausted_models_json() -> str:
    """JSON для отображения в панели настроек."""
    return json.dumps(list_exhausted_models(), ensure_ascii=False)
