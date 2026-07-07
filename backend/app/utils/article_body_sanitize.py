"""Удаление служебных меток структуры из текста статей."""

from __future__ import annotations

import re
from html import unescape

_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Метки из промптов / JSON-полей — не должны попадать в опубликованный текст.
_STRUCTURE_LABELS: frozenset[str] = frozenset(
    {
        "крючок",
        "hook",
        "quote",
        "цитата",
        "closing",
        "заключение",
        "интрига",
        "вывод",
        "лид",
        "неожиданный поворот",
        "источники",
        "анонс",
        "teaser",
        "body",
        "body_html",
        "image_prompt",
    }
)

_LABEL_LINE_RE = re.compile(
    r"^\s*(?:<b>\s*)?(?P<label>[^<:\n]+?)(?:\s*</b>)?\s*:?\s*$",
    re.IGNORECASE,
)
_NUMBERED_PREFIX_RE = re.compile(r"^\d+\)\s*")


def _strip_html_tags(text: str) -> str:
    """Убирает HTML-теги из фрагмента."""
    return unescape(_HTML_TAG_RE.sub("", text)).strip()


def _normalize_label(raw: str) -> str:
    """Нормализует строку для сравнения с набором меток."""
    text = _strip_html_tags(raw).strip().lower()
    text = _NUMBERED_PREFIX_RE.sub("", text)
    return text.rstrip(":").strip()


def _is_structure_label(line: str) -> bool:
    """True, если строка — только служебная метка раздела."""
    normalized = _normalize_label(line)
    if not normalized:
        return False
    if normalized in _STRUCTURE_LABELS:
        return True
    # «Неожиданный поворот:» с двоеточием в тексте метки
    for label in _STRUCTURE_LABELS:
        if normalized.startswith(label) and len(normalized) <= len(label) + 2:
            return True
    return False


def strip_article_structure_labels(html: str) -> str:
    """Убирает строки-служебные заголовки из HTML тела статьи.

    Args:
        html: HTML тела статьи.

    Returns:
        str: очищенный HTML.
    """
    if not html or not html.strip():
        return html

    paragraphs = re.split(r"\n\s*\n", html.strip())
    kept: list[str] = []
    for paragraph in paragraphs:
        lines = [line for line in paragraph.split("\n") if line.strip()]
        if not lines:
            continue
        if len(lines) == 1 and _is_structure_label(lines[0]):
            continue
        filtered = [line for line in lines if not _is_structure_label(line)]
        if filtered:
            kept.append("\n".join(filtered))

    return "\n\n".join(kept).strip()


def _normalize_compare_text(text: str) -> str:
    """Сжимает текст для сравнения абзацев."""
    cleaned = _strip_html_tags(text).lower()
    cleaned = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _extract_teaser_hook(teaser_html: str) -> str:
    """Извлекает текст крючка из HTML-анонса (без заголовка)."""
    blocks = [b.strip() for b in re.split(r"\n\s*\n", teaser_html.strip()) if b.strip()]
    if len(blocks) >= 2:
        return blocks[1]
    if blocks:
        first = blocks[0]
        if not re.match(r"^\s*<b>", first, re.IGNORECASE):
            return first
    return ""


def dedupe_teaser_hook_from_body(body_html: str, teaser_html: str) -> str:
    """Убирает из тела первый абзац, если он дублирует крючок из анонса.

    Args:
        body_html: HTML тела.
        teaser_html: HTML анонса.

    Returns:
        str: тело без дубликата.
    """
    hook = _normalize_compare_text(_extract_teaser_hook(teaser_html))
    if not hook or len(hook) < 25:
        return body_html

    paragraphs = re.split(r"\n\s*\n", body_html.strip())
    if not paragraphs:
        return body_html

    first_norm = _normalize_compare_text(paragraphs[0])
    if not first_norm:
        return body_html

    if first_norm == hook or hook in first_norm or first_norm in hook:
        return "\n\n".join(paragraphs[1:]).strip()

    return body_html


def sanitize_article_body_html(
    body_html: str,
    *,
    teaser_html: str | None = None,
) -> str:
    """Очищает тело статьи перед сохранением или публикацией.

    Args:
        body_html: HTML тела.
        teaser_html: HTML анонса (для удаления дубликата крючка).

    Returns:
        str: очищенное тело.
    """
    cleaned = strip_article_structure_labels(body_html)
    if teaser_html:
        cleaned = dedupe_teaser_hook_from_body(cleaned, teaser_html)
    return cleaned.strip()
