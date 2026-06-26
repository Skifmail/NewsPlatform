"""Валидация и очистка текста рерайта перед публикацией."""

import re

# Маркеры «утечки» chain-of-thought в ответ модели.
_LEAK_MARKERS = (
    "пользователь просит",
    "давайте разбер",
    "факты из оригинала",
    "важно перед переписыванием",
    "что важно для канала",
    "структура строгая",
    "**факты",
    "разберём исходную",
    "вот что у нас есть",
)

_HTML_POST_ANCHOR_RE = re.compile(
    r"(?:<p>\s*)?<b>.+",
    re.IGNORECASE | re.DOTALL,
)


def looks_like_rewrite_leak(text: str) -> bool:
    """Определяет, похож ли текст на рассуждения модели, а не на пост.

    Args:
        text: ответ рерайтера.

    Returns:
        bool: True если обнаружены признаки утечки рассуждений.
    """
    lowered = text.lower()
    if any(marker in lowered for marker in _LEAK_MARKERS):
        return True
    if len(text) > 200 and "<b>" not in lowered and "<blockquote" not in lowered:
        return True
    return False


def extract_publishable_rewrite(text: str) -> str | None:
    """Пытается вырезать финальный HTML-пост из ответа с рассуждениями.

    Args:
        text: сырой ответ модели.

    Returns:
        str | None: HTML поста или None.
    """
    stripped = text.strip()
    if not stripped:
        return None
    if not looks_like_rewrite_leak(stripped):
        return stripped

    match = _HTML_POST_ANCHOR_RE.search(stripped)
    if not match:
        return None
    candidate = match.group(0).strip()
    if "<b>" not in candidate.lower():
        return None
    return candidate


def is_publishable_rewrite(text: str) -> bool:
    """Проверяет, пригоден ли текст для публикации в Telegram.

    Args:
        text: итоговый HTML после нормализации.

    Returns:
        bool: True если пост выглядит валидным.
    """
    stripped = text.strip()
    if len(stripped) < 80:
        return False
    if "<b>" not in stripped.lower():
        return False
    if looks_like_rewrite_leak(stripped):
        return False
    return True


def sanitize_rewrite_output(text: str) -> str:
    """Очищает ответ рерайтера от рассуждений модели.

    Args:
        text: сырой ответ API.

    Returns:
        str: текст для нормализации HTML; может остаться пустым/невалидным.

    Raises:
        ValueError: если из ответа нельзя извлечь пост.
    """
    stripped = text.strip()
    if not stripped:
        msg = "Рерайт пустой"
        raise ValueError(msg)
    if not looks_like_rewrite_leak(stripped):
        return stripped
    extracted = extract_publishable_rewrite(stripped)
    if extracted and not looks_like_rewrite_leak(extracted):
        return extracted
    msg = "Модель вернула рассуждения вместо HTML-поста"
    raise ValueError(msg)
