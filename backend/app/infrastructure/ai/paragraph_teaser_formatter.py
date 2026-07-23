"""Форматирование Telegram-анонса для познавательного канала «Параграф»."""

from typing import Any


def is_paragraph_article_channel(channel_name: str) -> bool:
    """Определяет, нужен ли формат анонса канала «Параграф».

    Args:
        channel_name: название канала.

    Returns:
        bool: True для канала «Параграф».
    """
    return "параграф" in channel_name.lower()


def paragraph_writing_instructions(teaser_max_length: int) -> str:
    """Возвращает дополнительные инструкции для ArticleWriter (Параграф).

    Args:
        teaser_max_length: лимит анонса в Telegram.

    Returns:
        str: блок инструкций на русском.
    """
    return f"""Формат Telegram-анонса (поле teaser соберёт платформа — заполни структурные поля):

Ответь JSON с ключами:
title, body_html, image_prompt, hook, quote, closing.

- hook — 2–3 предложения-крючок; начни с 1 уместного эмодзи (🧠 💡 🔬 ✨ 🧪).
- quote — короткая яркая цитата или ключевая фраза из исследования (только реальные факты).
- closing — 1–2 предложения интриги, без спойлеров всей статьи.
- teaser — оставь пустой строкой "" (соберём автоматически).

body_html — основной текст для публикации в Telegram (не Telegraph): развёрнутая статья.
ЗАПРЕЩЕНО в body_html использовать служебные заголовки разделов:
«Крючок», «Hook», «Quote», «Цитата», «Closing», «Вывод», «Лид», «Неожиданный поворот»,
«Источники» и другие метки из этого списка полей JSON.
Содержимое hook/quote/closing — ТОЛЬКО в соответствующих JSON-полях, не дублируй в body_html.
Подзаголовки разделов — осмысленные формулировки по теме (<b>...</b>), не названия полей промпта.

image_prompt — только английский, 3–4 предложения.
Опиши детальную образовательную иллюстрацию с конкретными объектами из статьи:
точные предметы, научные элементы, материалы и текстуры, ракурс, освещение (мягкий студийный или натуральный), цветовая палитра.
Стиль: photorealism или high-quality 3D render, насыщенный деталями, передающий суть темы.
Абсолютно запрещено: люди, лица, тела, текст / буквы / цифры на изображении, интерфейсы, экраны.
Лимит карточки teaser после сборки: до {teaser_max_length} символов."""


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
