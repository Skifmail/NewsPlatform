"""Утилиты форматирования текста постов."""

import re
from html import unescape

MAX_REWRITE_LENGTH = 2000
# Лимиты Telegram Bot API (официальная документация core.telegram.org/bots/api).
TELEGRAM_BOT_CAPTION_MAX = 1024
TELEGRAM_MESSAGE_MAX = 4096
# Подпись к медиа через MTProto (аккаунт с Premium) — до 4096 видимых символов.
TELEGRAM_USER_CAPTION_MAX = 4096
# Лимит текста сообщения MAX Bot API (dev.max.ru).
MAX_MESSAGE_MAX = 4000
# Запас под кросс-промо футер и переносы строк при сборке длинного поста,
# чтобы блок «Источники» и ссылка на другую площадку не обрезались лимитом.
LONGFORM_FOOTER_RESERVE = 160
_SOURCE_LINK_LABEL = "Читать в источнике →"
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_INSTALL_HINT_RE = re.compile(
    r"\b(install|setup|docker|brew|apt|npm|cargo|pip|установ|разверт|деплой)\b",
    re.IGNORECASE,
)
_USE_HINT_RE = re.compile(
    r"\b(api|usage|how to|примера|использован|команд|настро)\b",
    re.IGNORECASE,
)
_DEVTOOLS_READ_MORE_CTAS = (
    "Как установить →",
    "Быстрый старт →",
    "Пошаговая инструкция →",
    "Как использовать →",
    "Примеры в репозитории →",
)
_PARAGRAPH_READ_MORE_CTAS = (
    "Узнать подробности →",
    "Читать разбор →",
    "Вся статья с примерами →",
    "Что важно знать →",
    "Подробности и факты →",
)
_GENERIC_READ_MORE_CTAS = (
    "Как это работает →",
    "Пошаговая инструкция →",
    "Подробности и примеры →",
    "Как использовать →",
    "Разбор с примерами →",
)


def build_source_link_html(source_url: str, label: str = _SOURCE_LINK_LABEL) -> str:
    """Собирает HTML-ссылку на источник для Telegram.

    Args:
        source_url: URL оригинальной статьи.
        label: текст ссылки.

    Returns:
        str: фрагмент `<a href="...">...</a>`.
    """
    escaped_url = source_url.replace('"', "%22")
    return f'<a href="{escaped_url}">{label}</a>'


def pick_article_read_more_label(
    *,
    channel_name: str = "",
    article_title: str = "",
    article_body: str = "",
    post_id: int | None = None,
) -> str:
    """Подбирает текст CTA-ссылки на полную статью (Telegraph).

    Args:
        channel_name: название канала.
        article_title: заголовок статьи.
        article_body: HTML тела статьи.
        post_id: ID поста для ротации формулировок.

    Returns:
        str: короткий призыв к переходу.
    """
    haystack = f"{article_title}\n{strip_html_tags(article_body)}"
    lowered_channel = channel_name.lower()

    if any(marker in lowered_channel for marker in ("github", "находк", "devtools")):
        pool = _DEVTOOLS_READ_MORE_CTAS
    elif "параграф" in lowered_channel:
        pool = _PARAGRAPH_READ_MORE_CTAS
    else:
        pool = _GENERIC_READ_MORE_CTAS

    if _INSTALL_HINT_RE.search(haystack):
        return "Как установить →"
    if _USE_HINT_RE.search(haystack):
        return "Как использовать →"

    index = (post_id or 0) % len(pool)
    return pool[index]


def build_article_read_more_html(
    url: str,
    *,
    channel_name: str = "",
    article_title: str = "",
    article_body: str = "",
    post_id: int | None = None,
) -> str:
    """Собирает заметную CTA-ссылку на полную статью.

    Telegram не поддерживает настоящие кнопки в HTML-тексте — делаем
    визуальный акцент: отдельная строка, эмодзи, жирный и подчёркнутый текст.

    Args:
        url: ссылка на Telegraph.
        channel_name: название канала.
        article_title: заголовок статьи.
        article_body: HTML тела статьи.
        post_id: ID поста для ротации формулировок.

    Returns:
        str: HTML-фрагмент для вставки в анонс.
    """
    label = pick_article_read_more_label(
        channel_name=channel_name,
        article_title=article_title,
        article_body=article_body,
        post_id=post_id,
    )
    escaped_url = url.replace('"', "%22")
    return f'<b>👉 <a href="{escaped_url}"><u>{label}</u></a></b>'


def ensure_source_link(text: str, source_url: str | None) -> str:
    """Добавляет ссылку на источник, если модель её не вставила.

    Args:
        text: текст после рерайта.
        source_url: URL оригинала.

    Returns:
        str: текст со ссылкой в конце (если URL задан).
    """
    if not source_url or not source_url.strip():
        return text.strip()
    normalized_url = source_url.strip()
    stripped = text.strip()
    if normalized_url in stripped:
        return stripped
    link = build_source_link_html(normalized_url)
    if link in stripped:
        return stripped
    # Модель могла вставить другой URL той же статьи — не дублируем ссылку.
    if re.search(r"<a\s+href=", stripped, re.IGNORECASE):
        return stripped
    if _SOURCE_LINK_LABEL in stripped:
        return stripped
    separator = "\n\n" if stripped else ""
    return f"{stripped}{separator}{link}"


def build_cross_promote_link_label(
    label: str | None,
    emoji_id: str | None = None,
    *,
    emoji_fallback: str = "⭕",
) -> str:
    """Собирает текст ссылки с опциональным анимированным эмодзи Telegram.

    Args:
        label: обычный текст ссылки.
        emoji_id: custom_emoji_id из Telegram (поле entities).
        emoji_fallback: запасной символ, если анимация недоступна.

    Returns:
        str: plain text или HTML с ``<tg-emoji>``.
    """
    text = (label or "Подписывайтесь в MAX →").strip()
    if not emoji_id or not emoji_id.strip():
        return text
    if "<tg-emoji" in text.lower():
        return text
    return f'<tg-emoji emoji-id="{emoji_id.strip()}">{emoji_fallback}</tg-emoji> {text}'


def append_cross_promote_footer(
    text: str,
    promote_url: str | None,
    promote_label: str | None = None,
    *,
    promote_emoji_id: str | None = None,
) -> str:
    """Добавляет в конец поста ссылку на другую площадку (перелив аудитории).

    Args:
        text: HTML поста.
        promote_url: URL канала на MAX/VK и т.д.
        promote_label: текст ссылки; если пусто — «Подписывайтесь в MAX →».
        promote_emoji_id: ID анимированного эмодзи Telegram для текста ссылки.

    Returns:
        str: текст со ссылкой в конце (если URL задан).
    """
    if not promote_url or not promote_url.strip():
        return text.strip()
    normalized_url = promote_url.strip()
    stripped = text.strip()
    if normalized_url in stripped:
        return stripped
    label = build_cross_promote_link_label(promote_label, promote_emoji_id)
    link = build_source_link_html(normalized_url, label)
    plain_label = promote_label or "Подписывайтесь в MAX →"
    if link in stripped or plain_label in stripped:
        return stripped
    separator = "\n\n" if stripped else ""
    return f"{stripped}{separator}{link}"


def cross_promote_footer_length(
    promote_url: str | None,
    promote_label: str | None = None,
    *,
    promote_emoji_id: str | None = None,
) -> int:
    """Длина кросс-промо футера, добавляемого в конец поста.

    Нужна, чтобы зарезервировать место под футер до обрезки тела по лимиту —
    иначе ссылка на другую площадку (например MAX) теряется при усечении.

    Args:
        promote_url: URL площадки.
        promote_label: текст ссылки.
        promote_emoji_id: ID анимированного эмодзи Telegram.

    Returns:
        int: число символов футера (с разделителем) или 0, если URL пуст.
    """
    if not promote_url or not promote_url.strip():
        return 0
    label = build_cross_promote_link_label(promote_label, promote_emoji_id)
    link = build_source_link_html(promote_url.strip(), label)
    return len("\n\n") + len(link)


def long_form_body_limit(*, platform: str, teaser_max_length: int) -> int:
    """Бюджет тела длинной статьи, при котором весь пост влезает в сообщение.

    Анонс (teaser) + тело + футер должны поместиться в одно сообщение
    площадки (Telegram 4096, MAX 4000), иначе обрезается хвост — блок
    «Источники» и кросс-промо ссылка.

    Args:
        platform: платформа канала (``telegram`` | ``max`` | ...).
        teaser_max_length: лимит анонса (резервируется под анонс).

    Returns:
        int: максимальная длина тела статьи в символах.
    """
    caption_limit = MAX_MESSAGE_MAX if platform == "max" else TELEGRAM_USER_CAPTION_MAX
    budget = caption_limit - teaser_max_length - LONGFORM_FOOTER_RESERVE
    return max(1500, budget)


def repair_telegram_html(text: str) -> str:
    """Чинит HTML перед отправкой в Telegram: убирает оборванные теги, закрывает открытые.

    Args:
        text: HTML поста.

    Returns:
        str: валидный для Bot API HTML.
    """
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    # Обрезка по лимиту могла оставить «<a href="...» без закрытия.
    cleaned = re.sub(r"<[^>]*$", "", cleaned).rstrip()
    if cleaned.endswith("…"):
        cleaned = cleaned[:-1].rstrip()
        cleaned = re.sub(r"<[^>]*$", "", cleaned).rstrip()

    for tag in ("blockquote", "b", "i", "a", "tg-emoji"):
        opens = len(re.findall(rf"<{tag}(?:\s[^>]*)?>", cleaned, re.IGNORECASE))
        closes = len(re.findall(rf"</{tag}>", cleaned, re.IGNORECASE))
        missing = opens - closes
        if missing > 0:
            cleaned += "".join(f"</{tag}>" for _ in range(missing))

    return cleaned.strip()


def clamp_rewrite_length(text: str, max_length: int = MAX_REWRITE_LENGTH) -> str:
    """Обрезает текст поста до допустимой длины.

    Args:
        text: итоговый текст.
        max_length: лимит символов.

    Returns:
        str: обрезанный и починенный HTML.
    """
    cleaned = repair_telegram_html(text.strip())
    if len(cleaned) <= max_length:
        return cleaned

    # Режем до лимита и убираем хвост внутри незакрытого тега.
    truncated = cleaned[: max_length - 1].rstrip()
    truncated = re.sub(r"<[^>]*$", "", truncated).rstrip()
    if truncated and not truncated.endswith("…"):
        truncated = f"{truncated}…"
    return repair_telegram_html(truncated)


_BLOCK_TAG_RE = re.compile(r"</?(?:p|blockquote)\b", re.IGNORECASE)
_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)


def normalize_telegram_html(text: str) -> str:
    """Приводит HTML поста к блочной структуре для Telegram Bot API.

    Абзацы разделяются пустой строкой (без ``<p>`` — тег не поддерживается API).
    Цитаты — в ``<blockquote expandable>``.

    Args:
        text: сырой ответ модели.

    Returns:
        str: нормализованный HTML.
    """
    cleaned = to_telegram_api_html(text)
    if not cleaned:
        return cleaned

    # Модель иногда кладёт blockquote внутрь абзаца — выносим отдельным блоком.
    if "<blockquote" in cleaned.lower():
        cleaned = re.sub(
            r"(?P<prefix>[^\n]*)\s*(<blockquote[^>]*>.*?</blockquote>)",
            r"\1\n\n\2",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )

    has_blocks = bool(_BLOCK_TAG_RE.search(cleaned)) or "<blockquote" in cleaned.lower()
    if not has_blocks:
        chunks = re.split(r"\n\s*\n", cleaned)
        parts: list[str] = []
        for chunk in chunks:
            piece = chunk.strip()
            if not piece:
                continue
            if piece.lower().startswith("<blockquote"):
                parts.append(_expand_blockquote(piece))
            else:
                parts.append(piece)
        cleaned = "\n\n".join(parts)
    else:
        cleaned = _expand_blockquote_tags(cleaned)
        cleaned = to_telegram_api_html(cleaned)

    return cleaned.strip()


def to_telegram_api_html(text: str) -> str:
    """Конвертирует HTML в разметку, допустимую Telegram Bot API.

    Убирает ``<p>`` (не поддерживается), сохраняет b, i, a, blockquote и переносы.

    Args:
        text: текст поста из БД или после рерайта.

    Returns:
        str: HTML для ``parse_mode=HTML``.
    """
    cleaned = text.strip()
    if not cleaned:
        return cleaned

    # Закрывающий </p> → разделитель абзацев до удаления открывающих тегов.
    cleaned = re.sub(r"</p>\s*", "\n\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<p[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = _BR_RE.sub("\n", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = _expand_blockquote_tags(cleaned)
    return cleaned.strip()


def _expand_blockquote(fragment: str) -> str:
    """Добавляет ``expandable`` к blockquote, если атрибут не задан.

    Args:
        fragment: HTML-фрагмент.

    Returns:
        str: blockquote с атрибутом expandable.
    """
    if "expandable" in fragment.lower():
        return fragment
    return re.sub(
        r"<blockquote\b",
        "<blockquote expandable",
        fragment,
        count=1,
        flags=re.IGNORECASE,
    )


def _expand_blockquote_tags(html: str) -> str:
    """Добавляет ``expandable`` ко всем blockquote в тексте.

    Args:
        html: HTML поста.

    Returns:
        str: обновлённый HTML.
    """
    return re.sub(
        r"<blockquote(?![^>]*\bexpandable\b)",
        "<blockquote expandable",
        html,
        flags=re.IGNORECASE,
    )


def to_max_api_html(text: str) -> str:
    """Конвертирует HTML поста в разметку MAX Bot API.

    MAX поддерживает HTML, близкий к Telegram, но без атрибута ``expandable``
    у ``blockquote``.

    Args:
        text: текст поста из БД или после рерайта.

    Returns:
        str: HTML для поля ``format=html`` в POST /messages.
    """
    cleaned = repair_telegram_html(to_telegram_api_html(text))
    cleaned = re.sub(
        r"<blockquote\s+expandable\b",
        "<blockquote",
        cleaned,
        flags=re.IGNORECASE,
    )
    if len(cleaned) <= MAX_MESSAGE_MAX:
        return cleaned
    truncated = cleaned[: MAX_MESSAGE_MAX - 1].rstrip()
    truncated = re.sub(r"<[^>]*$", "", truncated).rstrip()
    if truncated and not truncated.endswith("…"):
        truncated = f"{truncated}…"
    return repair_telegram_html(truncated)


def to_telethon_html(text: str) -> str:
    """HTML для публикации через Telethon (без ``expandable`` у blockquote).

    Args:
        text: текст поста.

    Returns:
        str: HTML для ``parse_mode=html`` в Telethon.
    """
    cleaned = repair_telegram_html(to_telegram_api_html(text))
    cleaned = re.sub(
        r"<blockquote\s+expandable\b",
        "<blockquote",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned


def build_article_telegram_text(
    *,
    article_title: str | None,
    teaser_html: str | None,
    body_html: str | None,
    max_length: int = TELEGRAM_USER_CAPTION_MAX,
) -> str:
    """Собирает полный текст статьи для одного сообщения Telegram.

    Карточка-анонс (teaser) + основной текст (body) в одном посте.

    Args:
        article_title: заголовок статьи.
        teaser_html: HTML карточки / крючка.
        body_html: основной HTML статьи.
        max_length: лимит символов в строке (Telethon Premium).

    Returns:
        str: готовый HTML поста.
    """
    parts: list[str] = []
    title = (article_title or "").strip()
    teaser = to_telethon_html((teaser_html or "").strip())
    body = to_telethon_html((body_html or "").strip())

    if teaser:
        parts.append(teaser)
    elif title:
        parts.append(f"<b>{title}</b>")

    if body:
        parts.append(body)

    text = "\n\n".join(part for part in parts if part).strip()
    text = repair_telegram_html(text)
    if len(text) <= max_length:
        return text

    truncated = text[: max_length - 1].rstrip()
    truncated = re.sub(r"<[^>]*$", "", truncated).rstrip()
    if truncated and not truncated.endswith("…"):
        truncated = f"{truncated}…"
    return repair_telegram_html(truncated)


def strip_html_tags(text: str) -> str:
    """Убирает HTML-теги для платформ без разметки (VK и др.).

    Args:
        text: текст с HTML.

    Returns:
        str: plain text.
    """
    without_tags = _HTML_TAG_RE.sub("", text)
    return unescape(without_tags).strip()
