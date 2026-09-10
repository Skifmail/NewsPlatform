"""Хэштеги-рубрики для фильтрации ленты в мессенджерах.

В Telegram/MAX клик по ``#тегу`` открывает поиск по каналу: читатель
листает только посты с этой меткой. Каталог намеренно узкий (4–5 рубрик),
чтобы не дробить архив.
"""

from __future__ import annotations

import re
from typing import Sequence

from app.domain.article_meta import ArticleMeta, parse_article_meta

# Основные рубрики познавательного канала «Параграф».
PARAGRAPH_HASHTAGS: tuple[str, ...] = (
    "#авиация",
    "#катастрофы",
    "#физика",
    "#космос",
    "#технологии",
)

# Запасной маппинг category → 1–2 тега, если модель не вернула hashtags.
CATEGORY_HASHTAG_FALLBACK: dict[str, tuple[str, ...]] = {
    "error": ("#катастрофы", "#технологии"),
    "everyday_object": ("#технологии", "#физика"),
    "history": ("#технологии", "#физика"),
    "science": ("#физика", "#космос"),
    "interactive": ("#технологии", "#физика"),
    "longform": ("#технологии", "#физика"),
}

# #катастрофы — только для category=error (аварии / инженерные провалы).
_DISASTER_TAG = "#катастрофы"
_DISASTER_CATEGORIES = frozenset({"error"})

_HASHTAG_TOKEN_RE = re.compile(r"#?[^\s#]+", re.UNICODE)
_MAX_TAGS_PER_POST = 2


def normalize_hashtag(raw: str) -> str:
    """Нормализует один тег к виду ``#слово`` в нижнем регистре.

    Args:
        raw: фрагмент с ``#`` или без.

    Returns:
        str: нормализованный тег или пустая строка.
    """
    token = (raw or "").strip().lstrip("#").strip()
    if not token:
        return ""
    # Убираем знаки препинания по краям (модель иногда ставит запятую).
    token = token.strip(".,;:!?)(")
    if not token:
        return ""
    return f"#{token.lower()}"


def parse_hashtag_list(raw: str | None | Sequence[str]) -> list[str]:
    """Разбирает список хэштегов из строки или последовательности.

    Строка может быть через пробел, запятую или перевод строки:
    ``#авиация #физика`` / ``авиация, физика``.

    Args:
        raw: строка канала, JSON-массив или список строк.

    Returns:
        list[str]: уникальные нормализованные теги (порядок сохранён).
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        if not raw.strip():
            return []
        tokens = _HASHTAG_TOKEN_RE.findall(raw.replace(",", " "))
    else:
        tokens = [str(item) for item in raw]

    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        tag = normalize_hashtag(token)
        if not tag or tag in seen:
            continue
        seen.add(tag)
        result.append(tag)
    return result


def format_hashtag_line(tags: Sequence[str]) -> str:
    """Собирает строку хэштегов для конца поста.

    Args:
        tags: нормализованные теги.

    Returns:
        str: ``#авиация #физика`` или пустая строка.
    """
    cleaned = parse_hashtag_list(list(tags))
    return " ".join(cleaned)


def hashtag_line_length(tags: Sequence[str]) -> int:
    """Длина блока хэштегов с разделителем (для резерва лимита сообщения).

    Args:
        tags: теги поста.

    Returns:
        int: число символов включая ``\\n\\n``, или 0.
    """
    line = format_hashtag_line(tags)
    if not line:
        return 0
    return len("\n\n") + len(line)


def build_pin_menu_text(tags: Sequence[str] | None = None) -> str:
    """Текст закрепа: интерактивное меню рубрик канала.

    Args:
        tags: каталог рубрик; по умолчанию — рубрики Параграфа.

    Returns:
        str: готовый текст для закреплённого сообщения.
    """
    catalog = parse_hashtag_list(list(tags) if tags is not None else PARAGRAPH_HASHTAGS)
    if not catalog:
        catalog = list(PARAGRAPH_HASHTAGS)
    lines = "\n".join(catalog)
    return (
        "Рубрики канала — нажмите тег, чтобы читать только эту тему:\n"
        f"{lines}\n\n"
        "В конце каждого поста стоит 1–2 таких метки."
    )


def default_catalog_for_channel(channel_name: str | None) -> list[str]:
    """Каталог по умолчанию для канала (Параграф → 5 рубрик).

    Args:
        channel_name: название канала.

    Returns:
        list[str]: теги или пустой список.
    """
    name = (channel_name or "").lower()
    if "параграф" in name:
        return list(PARAGRAPH_HASHTAGS)
    return []


def allowed_catalog(
    channel_hashtags: str | None,
    *,
    channel_name: str | None = None,
) -> list[str]:
    """Разрешённый каталог тегов канала.

    Args:
        channel_hashtags: поле ``Channel.hashtags``.
        channel_name: для fallback на каталог Параграфа.

    Returns:
        list[str]: разрешённые теги.
    """
    configured = parse_hashtag_list(channel_hashtags)
    if configured:
        return configured
    return default_catalog_for_channel(channel_name)


def resolve_post_hashtags(
    *,
    meta: ArticleMeta | None = None,
    article_meta_raw: str | None = None,
    channel_hashtags: str | None = None,
    channel_name: str | None = None,
    max_tags: int = _MAX_TAGS_PER_POST,
) -> list[str]:
    """Выбирает 1–2 хэштега для публикации поста.

    Порядок приоритета:
    1. ``article_meta.hashtags`` (выбор модели), отфильтрованные по каталогу;
    2. fallback по ``article_meta.category``;
    3. пусто, если каталог канала пуст.

    Args:
        meta: уже распарсенные метаданные.
        article_meta_raw: JSON из БД, если meta не передан.
        channel_hashtags: каталог из настроек канала.
        channel_name: имя канала для каталога по умолчанию.
        max_tags: максимум тегов в посте (обычно 2).

    Returns:
        list[str]: 0..max_tags тегов.
    """
    catalog = allowed_catalog(channel_hashtags, channel_name=channel_name)
    if not catalog:
        return []

    catalog_set = set(catalog)
    resolved = meta if meta is not None else parse_article_meta(article_meta_raw)
    category = resolved.category.strip().lower()

    picked = [tag for tag in parse_hashtag_list(resolved.hashtags) if tag in catalog_set]
    # Модель часто ставит #катастрофы на любую «драму» (история вулкана, пожар
    # реки). Оставляем этот тег только для category=error.
    if _DISASTER_TAG in picked and category not in _DISASTER_CATEGORIES:
        picked = [tag for tag in picked if tag != _DISASTER_TAG]

    if not picked and category:
        fallback = CATEGORY_HASHTAG_FALLBACK.get(category, ())
        picked = [tag for tag in fallback if tag in catalog_set]

    return picked[: max(1, max_tags)]


def resolve_hashtags_for_publish(
    *,
    article_meta_raw: str | None,
    channel_hashtags: str | None,
    channel_name: str | None,
) -> list[str]:
    """Удобная обёртка для паблишеров и API-ответов.

    Args:
        article_meta_raw: JSON article_meta поста.
        channel_hashtags: Channel.hashtags.
        channel_name: Channel.name.

    Returns:
        list[str]: теги для конца поста.
    """
    return resolve_post_hashtags(
        article_meta_raw=article_meta_raw,
        channel_hashtags=channel_hashtags,
        channel_name=channel_name,
    )
