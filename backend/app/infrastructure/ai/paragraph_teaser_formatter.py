"""Форматирование Telegram-анонса для познавательного канала «Параграф»."""

from typing import Any

from app.utils.safe_format import safe_format


def is_paragraph_article_channel(channel_name: str) -> bool:
    """Определяет, нужен ли формат анонса канала «Параграф».

    Args:
        channel_name: название канала.

    Returns:
        bool: True для канала «Параграф».
    """
    return "параграф" in channel_name.lower()


def paragraph_writing_instructions(template: str, teaser_max_length: int) -> str:
    """Собирает инструкции для ArticleWriter (Параграф) из шаблона панели промптов.

    Текст редактируется в панели промптов
    (prompt_templates: writing.paragraph_instructions, переменная {teaser_max_length}).

    Args:
        template: шаблон инструкций.
        teaser_max_length: лимит анонса в Telegram.

    Returns:
        str: блок инструкций на русском.
    """
    return safe_format(template, teaser_max_length=teaser_max_length)


def build_paragraph_teaser(
    data: dict[str, Any],
    *,
    teaser_max_length: int,
) -> str:
    """Собирает HTML-анонс в стиле канала «Параграф».

    Args:
        data: поля из ответа модели.
        teaser_max_length: лимит длины.

    Returns:
        str: HTML для Telegram.
    """
    title = str(data.get("title", "")).strip()
    hook = str(data.get("hook") or data.get("teaser") or "").strip()
    quote = _normalize_quote(str(data.get("quote") or ""))
    closing = str(data.get("closing") or "").strip()

    lines: list[str] = []
    if title:
        lines.append(f"<b>{title}</b>")
    if hook:
        lines.append(f"\n{hook}")
    if quote:
        lines.append(f"\n<blockquote>«{quote}»</blockquote>")
    if closing:
        lines.append(f"\n{closing}")

    teaser = "\n".join(lines).strip()
    if not teaser and title:
        teaser = f"<b>{title}</b>"
    if len(teaser) > teaser_max_length:
        teaser = _truncate_teaser(lines, teaser_max_length)
    return teaser


def _normalize_quote(raw: str) -> str:
    """Убирает лишние кавычки из цитаты.

    Args:
        raw: цитата от модели.

    Returns:
        str: очищенная цитата.
    """
    cleaned = raw.strip().strip("«»\"'")
    return cleaned


def _truncate_teaser(lines: list[str], max_length: int) -> str:
    """Укорачивает анонс, сохраняя структуру.

    Args:
        lines: блоки HTML.
        max_length: лимит символов.

    Returns:
        str: укороченный анонс.
    """
    teaser = "\n".join(lines).strip()
    if len(teaser) <= max_length:
        return teaser
    # Сначала убираем closing, затем quote — заголовок и hook важнее.
    if len(lines) > 3:
        shortened = "\n".join(lines[:-1]).strip()
        if len(shortened) <= max_length:
            return shortened
    if len(lines) > 2:
        shortened = "\n".join(lines[:2]).strip()
        if len(shortened) <= max_length:
            return shortened
    return f"{teaser[: max_length - 1].rstrip()}…"
