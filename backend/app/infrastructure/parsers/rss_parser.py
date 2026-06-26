"""RSS/Atom парсер на feedparser + httpx."""

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import feedparser
import httpx
from loguru import logger

from app.domain.entities import RawPostDTO
from app.infrastructure.models.source import Source
from app.infrastructure.parsers.base import BaseParser
from app.infrastructure.parsers.image_extract import extract_image_from_rss_entry

_USER_AGENT = "Mozilla/5.0 (compatible; NewsPlatform/1.0; +https://github.com)"
_FETCH_TIMEOUT = 35.0
_MAX_ENTRIES = 50


class RssParser(BaseParser):
    """Парсер RSS-лент."""

    async def fetch_new(self, source: Source) -> list[RawPostDTO]:
        """Парсит RSS-ленту по HTTP с User-Agent.

        Args:
            source: источник с URL ленты.

        Returns:
            list[RawPostDTO]: записи ленты (до 50 последних).
        """
        try:
            async with httpx.AsyncClient(
                timeout=_FETCH_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = await client.get(source.url)
                response.raise_for_status()
                content = response.content
        except httpx.HTTPError as exc:
            logger.warning(
                "RSS HTTP failed",
                source_id=source.id,
                url=source.url,
                error=str(exc),
            )
            return []

        feed = feedparser.parse(content)
        if feed.bozo and not feed.entries:
            logger.warning(
                "RSS parse failed",
                source_id=source.id,
                url=source.url,
                error=str(getattr(feed, "bozo_exception", "")),
            )
            return []

        posts: list[RawPostDTO] = []
        for entry in feed.entries[:_MAX_ENTRIES]:
            external_id = (
                entry.get("id")
                or entry.get("guid")
                or entry.get("link")
                or entry.get("title", "")
            )
            content_text = ""
            if entry.get("summary"):
                content_text = entry.summary
            elif entry.get("description"):
                content_text = entry.description
            elif entry.get("content"):
                content_text = entry.content[0].get("value", "")
            if not content_text and entry.get("title"):
                content_text = entry.title

            published_at = None
            if entry.get("published_parsed"):
                published_at = datetime(*entry.published_parsed[:6], tzinfo=UTC)
            elif entry.get("updated_parsed"):
                published_at = datetime(*entry.updated_parsed[:6], tzinfo=UTC)
            elif entry.get("published"):
                try:
                    published_at = parsedate_to_datetime(entry.published)
                    if published_at.tzinfo is None:
                        published_at = published_at.replace(tzinfo=UTC)
                except (TypeError, ValueError):
                    published_at = None

            entry_link = entry.get("link")
            image_url = extract_image_from_rss_entry(entry, entry_link)

            posts.append(
                RawPostDTO(
                    external_id=str(external_id),
                    title=entry.get("title"),
                    content=content_text,
                    url=entry.get("link"),
                    image_url=image_url,
                    topic=source.topic,
                    published_at=published_at,
                )
            )
        logger.info(
            "RSS fetched",
            source_id=source.id,
            source_name=source.name,
            count=len(posts),
            http_status=response.status_code,
        )
        return posts
