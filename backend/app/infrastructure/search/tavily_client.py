"""Клиент Tavily Search API."""

from dataclasses import dataclass

import httpx
from loguru import logger

from app.core.config import get_settings


@dataclass(frozen=True)
class TavilySearchResult:
    """Один результат поиска Tavily."""

    title: str
    url: str
    content: str


class TavilyClient:
    """Асинхронный клиент Tavily для веб-исследования."""

    _API_URL = "https://api.tavily.com/search"

    async def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        search_depth: str = "advanced",
    ) -> list[TavilySearchResult]:
        """Выполняет поиск по запросу.

        Args:
            query: поисковый запрос.
            max_results: лимит результатов.
            search_depth: basic | advanced.

        Returns:
            list[TavilySearchResult]: результаты поиска.

        Raises:
            RuntimeError: при отсутствии ключа или ошибке API.
        """
        settings = get_settings()
        api_key = settings.tavily_api_key.strip()
        if not api_key:
            msg = (
                "TAVILY_API_KEY не задан — добавьте ключ в .env "
                "(https://tavily.com)"
            )
            raise RuntimeError(msg)

        payload = {
            "api_key": api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": False,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self._API_URL, json=payload)
            if response.status_code != 200:
                logger.error(
                    "Tavily API error",
                    status=response.status_code,
                    body=response.text[:500],
                )
                msg = f"Tavily API error: {response.status_code}"
                raise RuntimeError(msg)
            data = response.json()

        results: list[TavilySearchResult] = []
        for item in data.get("results") or []:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url:
                continue
            results.append(
                TavilySearchResult(
                    title=str(item.get("title") or url),
                    url=url,
                    content=str(item.get("content") or "")[:2000],
                )
            )
        logger.info("Tavily search done", query=query, count=len(results))
        return results
