"""Форматирование анонса для познавательного канала «Параграф»."""

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

    Args:
        template: шаблон инструкций.
        teaser_max_length: лимит анонса.

    Returns:
        str: блок инструкций на русском.
    """
    return safe_format(template, teaser_max_length=teaser_max_length)


def build_paragraph_teaser(
    data: dict[str, Any],
    *,
    teaser_max_length: int,
) -> str:
    """Собирает HTML-анонс «Параграф» без обязательной цитаты.

    Структура: заголовок → hook → (опциональная цитата) → вопрос/closing.

    Args:
        data: поля из ответа модели.
        teaser_max_length: лимит длины.

    Returns:
        str: HTML для публикации.
    """
    title = str(data.get("title", "")).strip()
    hook = str(
        data.get("hook") or data.get("post_text") or data.get("teaser") or ""
    ).strip()
    # Цитата только если модель явно дала осмысленную (не обязательна).
    quote = _normalize_quote(str(data.get("quote") or ""))
    closing = str(
        data.get("interaction_question") or data.get("closing") or ""
    ).strip()

    # Если hook — это уже полный post_text, не дублируем closing внутри.
    lines: list[str] = []
    if title:
        lines.append(f"<b>{title}</b>")
    if hook:
        lines.append(f"\n{hook}")
    if quote and _quote_is_useful(quote, hook):
        lines.append(f"\n<blockquote>«{quote}»</blockquote>")
    if closing and closing not in hook:
        lines.append(f"\n{closing}")

    teaser = "\n".join(lines).strip()
    if not teaser and title:
        teaser = f"<b>{title}</b>"
    if len(teaser) > teaser_max_length:
        teaser = _truncate_teaser(lines, teaser_max_length)
    return teaser


def _normalize_quote(raw: str) -> str:
    """Убирает лишние кавычки из цитаты."""
    return raw.strip().strip("«»\"'")


def _quote_is_useful(quote: str, hook: str) -> bool:
    """Отсекает цитаты, которые просто повторяют hook или на английском без кириллицы."""
    if len(quote) < 12:
        return False
    q = quote.lower()
    h = hook.lower()
    if q in h or h in q:
        return False
    has_cyr = any("а" <= ch <= "я" or ch == "ё" for ch in q)
    has_lat = any("a" <= ch <= "z" for ch in q)
    if has_lat and not has_cyr:
        return False
    return True


def _truncate_teaser(lines: list[str], max_length: int) -> str:
    """Укорачивает анонс, сохраняя структуру (без обрезки mid-tag)."""
    teaser = "\n".join(lines).strip()
    if len(teaser) <= max_length:
        return teaser
    if len(lines) > 3:
        shortened = "\n".join(lines[:-1]).strip()
        if len(shortened) <= max_length:
            return shortened
    if len(lines) > 2:
        shortened = "\n".join(lines[:2]).strip()
        if len(shortened) <= max_length:
            return shortened
    # Режем по границе предложения, не mid-HTML.
    cut = teaser[: max_length - 1]
    for sep in (". ", "! ", "? ", "\n"):
        pos = cut.rfind(sep)
        if pos >= max_length // 2:
            return cut[: pos + 1].rstrip() + "…"
    cleaned = cut.rsplit(" ", 1)[0].rstrip()
    cleaned = cleaned.rsplit("<", 1)[0].rstrip() if "<" in cleaned[-20:] else cleaned
    return f"{cleaned}…"
