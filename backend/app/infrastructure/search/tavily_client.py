"""Клиент Tavily Search API."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
from loguru import logger

from app.infrastructure.search.tavily_key_chain import (
    TavilyKeyEntry,
    is_quota_exhausted,
    key_fingerprint,
    mark_key_exhausted,
    ordered_keys_for_use,
    resolve_keys,
)


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
        keys_raw: str | None = None,
        active_key_id: str | None = None,
        auto_switch: bool = True,
    ) -> list[TavilySearchResult]:
        """Выполняет поиск по запросу с failover по ключам.

        Args:
            query: поисковый запрос.
            max_results: лимит результатов.
            search_depth: basic | advanced.
            keys_raw: JSON ключей из настроек БД.
            active_key_id: выбранный вручную ключ.
            auto_switch: переключаться при исчерпании лимита.

        Returns:
            list[TavilySearchResult]: результаты поиска.

        Raises:
            RuntimeError: при отсутствии ключей или ошибке API.
        """
        keys = resolve_keys(keys_raw)
        if not keys:
            msg = (
                "Tavily API-ключ не задан — добавьте TAVILY_API_KEY в .env "
                "или ключ в настройках панели (https://tavily.com)"
            )
            raise RuntimeError(msg)

        candidates = ordered_keys_for_use(
            keys,
            active_key_id=active_key_id,
            auto_switch=auto_switch,
        )
        if not candidates:
            msg = (
                "Все ключи Tavily помечены как исчерпанные в этом месяце — "
                "добавьте новый ключ или дождитесь сброса лимита"
            )
            raise RuntimeError(msg)

        last_error = "Tavily API error"
        for entry in candidates:
            try:
                return await self._search_with_key(
                    entry,
                    query,
                    max_results=max_results,
                    search_depth=search_depth,
                )
            except _TavilyQuotaError as exc:
                mark_key_exhausted(entry.id)
                last_error = str(exc)
                logger.warning(
                    "Tavily quota exhausted, trying next key",
                    key_id=entry.id,
                    fingerprint=key_fingerprint(entry.key),
                    auto_switch=auto_switch,
                )
                if not auto_switch:
                    break
                continue
            except RuntimeError as exc:
                last_error = str(exc)
                logger.warning(
                    "Tavily search failed for key",
                    key_id=entry.id,
                    fingerprint=key_fingerprint(entry.key),
                    error=last_error,
                )
                if not auto_switch:
                    break
                continue

        raise RuntimeError(last_error)

    async def _search_with_key(
        self,
        entry: TavilyKeyEntry,
        query: str,
        *,
        max_results: int,
        search_depth: str,
    ) -> list[TavilySearchResult]:
        """Выполняет один поисковый запрос конкретным ключом.

        Args:
            entry: ключ из цепочки.
            query: поисковый запрос.
            max_results: лимит результатов.
            search_depth: basic | advanced.

        Returns:
            list[TavilySearchResult]: результаты.

        Raises:
            _TavilyQuotaError: кредиты исчерпаны.
            RuntimeError: другая ошибка API.
        """
        payload = {
            "api_key": entry.key,
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "include_answer": False,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self._API_URL, json=payload)
            body_text = response.text[:500]
            if response.status_code != 200:
                logger.error(
                    "Tavily API error",
                    status=response.status_code,
                    body=body_text,
                    key_id=entry.id,
                    fingerprint=key_fingerprint(entry.key),
                )
                if is_quota_exhausted(
                    status_code=response.status_code,
                    body_text=body_text,
                ):
                    raise _TavilyQuotaError(
                        f"Tavily quota exhausted for key {entry.id}: "
                        f"HTTP {response.status_code}"
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
        logger.info(
            "Tavily search done",
            query=query,
            count=len(results),
            key_id=entry.id,
            fingerprint=key_fingerprint(entry.key),
        )
        return results


class _TavilyQuotaError(RuntimeError):
    """Исчерпание кредитов Tavily для текущего ключа."""
