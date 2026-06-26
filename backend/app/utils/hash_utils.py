"""Утилиты хеширования для дедупликации."""

import hashlib
import re


def normalize_text(text: str) -> str:
    """Нормализует текст для сравнения.

    Args:
        text: исходный текст.

    Returns:
        str: нормализованная строка.
    """
    cleaned = re.sub(r"\s+", " ", text.strip().lower())
    return cleaned


def content_hash(text: str) -> str:
    """SHA256 хеш нормализованного текста.

    Args:
        text: исходный текст.

    Returns:
        str: hex-дайджест.
    """
    return hashlib.sha256(normalize_text(text).encode()).hexdigest()
