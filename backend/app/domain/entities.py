"""Доменные сущности (без зависимостей от ORM)."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RawPostDTO:
    """DTO сырого поста от парсера.

    Args:
        external_id: уникальный ID в источнике.
        title: заголовок.
        content: текст.
        url: ссылка на оригинал.
        image_url: URL картинки.
        topic: тематика.
        published_at: дата в источнике.
    """

    external_id: str
    title: str | None
    content: str
    url: str | None
    image_url: str | None
    topic: str
    published_at: datetime | None
