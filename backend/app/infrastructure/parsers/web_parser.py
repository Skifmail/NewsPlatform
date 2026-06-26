"""Веб-скрапер httpx + BeautifulSoup."""

import json
from datetime import UTC, datetime
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup
from loguru import logger

from app.domain.entities import RawPostDTO
from app.infrastructure.models.source import Source
from app.infrastructure.parsers.base import BaseParser
from app.infrastructure.parsers.image_extract import (
    extract_image_from_html,
    normalize_image_url,
)


class WebParser(BaseParser):
    """Парсит страницы по CSS-селекторам из parser_config."""

    async def fetch_new(self, source: Source) -> list[RawPostDTO]:
        """Скрапит одну или список страниц.

        Args:
            source: источник с url и parser_config JSON.

        Returns:
            list[RawPostDTO]: посты.
        """
        config: dict[str, str] = {}
        if source.parser_config:
            try:
                config = json.loads(source.parser_config)
            except json.JSONDecodeError:
                logger.error("Invalid parser_config", source_id=source.id)
                return []

        title_sel = config.get("title", "h1")
        content_sel = config.get("content", "article")
        list_sel = config.get("list", "")
        link_attr = config.get("link_attr", "href")

        posts: list[RawPostDTO] = []
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            if list_sel:
                resp = await client.get(source.url)
                resp.raise_for_status()
                soup = BeautifulSoup(resp.text, "lxml")
                for item in soup.select(list_sel)[:20]:
                    link = item.get(link_attr)
                    if not link:
                        continue
                    page_url = urljoin(source.url, str(link))
                    post = await self._parse_page(
                        client, page_url, title_sel, content_sel, source.topic
                    )
                    if post:
                        posts.append(post)
            else:
                post = await self._parse_page(
                    client, source.url, title_sel, content_sel, source.topic
                )
                if post:
                    posts.append(post)

        logger.info("Web fetched", source_id=source.id, count=len(posts))
        return posts

    async def _parse_page(
        self,
        client: httpx.AsyncClient,
        url: str,
        title_sel: str,
        content_sel: str,
        topic: str,
    ) -> RawPostDTO | None:
        """Парсит одну страницу.

        Args:
            client: HTTP-клиент.
            url: URL страницы.
            title_sel: селектор заголовка.
            content_sel: селектор контента.
            topic: тематика.

        Returns:
            RawPostDTO | None: пост или None.
        """
        try:
            resp = await client.get(url)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Web page fetch failed", url=url, error=str(exc))
            return None

        soup = BeautifulSoup(resp.text, "lxml")
        title_el = soup.select_one(title_sel)
        content_el = soup.select_one(content_sel)
        if not content_el:
            return None

        title = title_el.get_text(strip=True) if title_el else None
        content = content_el.get_text(separator="\n", strip=True)
        if len(content) < 50:
            return None

        image_url = extract_image_from_html(resp.text, url)
        if not image_url:
            img = content_el.find("img")
            if img and img.get("src"):
                image_url = normalize_image_url(str(img["src"]), url)

        return RawPostDTO(
            external_id=url,
            title=title,
            content=content,
            url=url,
            image_url=image_url,
            topic=topic,
            published_at=datetime.now(UTC),
        )
