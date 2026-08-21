"""Метаданные статьи Параграф: интерактив, обложка, сущности."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ArticleMeta:
    """Структурированные метаданные черновика/поста Параграф.

    Attributes:
        category: рубрика (ошибка / история вещи / …).
        cover_title: короткий заголовок на обложку (2–5 слов).
        interaction_question: вопрос для вовлечения.
        button_options: варианты callback-кнопок (2–3).
        entities: ключевые сущности темы.
        claims_to_verify: утверждения для фактчека.
        source_urls: URL источников.
        topic_queue_item_id: ID темы из редакционной очереди.
        format_variant: short | standard | long | video.
    """

    category: str = ""
    cover_title: str = ""
    interaction_question: str = ""
    button_options: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)
    claims_to_verify: list[str] = field(default_factory=list)
    source_urls: list[str] = field(default_factory=list)
    topic_queue_item_id: str | None = None
    format_variant: str = "standard"

    def to_dict(self) -> dict[str, Any]:
        """Сериализует в dict."""
        return asdict(self)


def parse_article_meta(raw: str | None) -> ArticleMeta:
    """Парсит JSON article_meta.

    Args:
        raw: JSON из БД.

    Returns:
        ArticleMeta: метаданные или пустой объект.
    """
    if not raw or not str(raw).strip():
        return ArticleMeta()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ArticleMeta()
    if not isinstance(data, dict):
        return ArticleMeta()
    return article_meta_from_dict(data)


def serialize_article_meta(meta: ArticleMeta) -> str:
    """Сериализует метаданные в JSON.

    Args:
        meta: объект метаданных.

    Returns:
        str: JSON.
    """
    return json.dumps(meta.to_dict(), ensure_ascii=False)


def article_meta_from_dict(data: dict[str, Any]) -> ArticleMeta:
    """Собирает ArticleMeta из dict ответа модели / БД.

    Args:
        data: словарь полей.

    Returns:
        ArticleMeta: нормализованные метаданные.
    """
    buttons = data.get("button_options") or data.get("buttons") or []
    if isinstance(buttons, str):
        buttons = [b.strip() for b in buttons.split("|") if b.strip()]
    elif not isinstance(buttons, list):
        buttons = []
    buttons = [str(b).strip() for b in buttons if str(b).strip()][:4]

    def _str_list(key: str) -> list[str]:
        raw = data.get(key) or []
        if isinstance(raw, str):
            return [raw.strip()] if raw.strip() else []
        if not isinstance(raw, list):
            return []
        return [str(x).strip() for x in raw if str(x).strip()]

    cover = str(data.get("cover_title") or "").strip()
    if not cover:
        title = str(data.get("title") or "").strip()
        cover = _shorten_cover_title(title)

    return ArticleMeta(
        category=str(data.get("category") or "").strip(),
        cover_title=cover,
        interaction_question=str(
            data.get("interaction_question") or data.get("closing") or ""
        ).strip(),
        button_options=buttons,
        entities=_str_list("entities"),
        claims_to_verify=_str_list("claims_to_verify"),
        source_urls=_str_list("source_urls"),
        topic_queue_item_id=(
            str(data["topic_queue_item_id"])
            if data.get("topic_queue_item_id")
            else None
        ),
        format_variant=str(data.get("format_variant") or "standard").strip()
        or "standard",
    )


def _shorten_cover_title(title: str, max_words: int = 5) -> str:
    """Укорачивает заголовок до короткой обложечной фразы.

    Args:
        title: полный заголовок.
        max_words: максимум слов.

    Returns:
        str: короткая фраза в верхнем регистре.
    """
    words = [w for w in title.replace("—", " ").replace(":", " ").split() if w]
    short = " ".join(words[:max_words]).strip(" .,-")
    return short.upper() if short else ""
