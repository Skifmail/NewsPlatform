"""Доменные модели и ключи для режима статей."""

import json
from dataclasses import dataclass

ARTICLE_TOPIC_HISTORY_PREFIX = "article_topic_history_"
ARTICLE_SCHEDULER_KEY_PREFIX = "scheduler_last_article_"


def article_scheduler_key(channel_id: int) -> str:
    """Ключ БД для времени последней генерации статьи канала.

    Args:
        channel_id: ID канала.

    Returns:
        str: ключ settings.
    """
    return f"{ARTICLE_SCHEDULER_KEY_PREFIX}{channel_id}"


def article_topic_history_key(channel_id: int) -> str:
    """Ключ БД для истории тем канала.

    Args:
        channel_id: ID канала.

    Returns:
        str: ключ settings.
    """
    return f"{ARTICLE_TOPIC_HISTORY_PREFIX}{channel_id}"


@dataclass(frozen=True)
class ArticleTopicPlan:
    """План темы и поисковых запросов."""

    topic: str
    angle: str
    search_queries: list[str]


@dataclass(frozen=True)
class ResearchSource:
    """Источник из веб-поиска."""

    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class ArticleDraft:
    """Черновик статьи от модели."""

    title: str
    teaser: str
    body_html: str
    image_prompt: str
    repo_url: str | None = None
    greeting_text: str = ""
    article_meta_json: str | None = None


def parse_topic_history(raw: str) -> list[str]:
    """Парсит JSON-список недавних тем.

    Args:
        raw: значение из settings.

    Returns:
        list[str]: темы от новых к старым.
    """
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data if item]


def serialize_topic_history(topics: list[str], limit: int = 80) -> str:
    """Сериализует историю тем в JSON.

    Args:
        topics: темы от новых к старым.
        limit: максимум записей.

    Returns:
        str: JSON-массив.
    """
    return json.dumps(topics[:limit], ensure_ascii=False)


def serialize_research_sources(sources: list[ResearchSource]) -> str:
    """Сериализует источники исследования в JSON.

    Args:
        sources: найденные источники.

    Returns:
        str: JSON для поля research_sources.
    """
    payload = [
        {"title": s.title, "url": s.url, "snippet": s.snippet} for s in sources
    ]
    return json.dumps(payload, ensure_ascii=False)
