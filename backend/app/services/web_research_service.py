"""Веб-исследование через Tavily."""

from loguru import logger

from app.domain.article import ResearchSource
from app.infrastructure.search.tavily_client import TavilyClient
from app.infrastructure.search.tavily_key_chain import resolve_keys

_MAX_CONTEXT_CHARS = 12_000
_MAX_SNIPPET = 1200


class WebResearchService:
    """Собирает контекст из интернета для написания статьи."""

    def __init__(self, client: TavilyClient | None = None) -> None:
        self._client = client or TavilyClient()

    async def research(
        self,
        queries: list[str],
        *,
        keys_raw: str | None = None,
        active_key_id: str | None = None,
        auto_switch: bool = True,
    ) -> tuple[str, list[ResearchSource]]:
        """Выполняет поиск и формирует текстовый контекст.

        Args:
            queries: поисковые запросы (2–3).
            keys_raw: JSON ключей Tavily из настроек БД.
            active_key_id: выбранный вручную ключ.
            auto_switch: автопереключение при исчерпании лимита.

        Returns:
            tuple[str, list[ResearchSource]]: контекст для промпта и источники.

        Raises:
            RuntimeError: при полном провале поиска.
        """
        seen_urls: set[str] = set()
        sources: list[ResearchSource] = []
        blocks: list[str] = []

        for query in queries[:3]:
            try:
                results = await self._client.search(
                    query,
                    max_results=5,
                    keys_raw=keys_raw,
                    active_key_id=active_key_id,
                    auto_switch=auto_switch,
                )
            except Exception as exc:
                logger.warning("Tavily query failed", query=query, error=str(exc))
                continue
            for item in results:
                if item.url in seen_urls:
                    continue
                seen_urls.add(item.url)
                snippet = item.content[:_MAX_SNIPPET]
                sources.append(
                    ResearchSource(
                        title=item.title,
                        url=item.url,
                        snippet=snippet,
                    )
                )
                blocks.append(
                    f"### {item.title}\nURL: {item.url}\n{snippet}\n"
                )

        if not sources:
            if not resolve_keys(keys_raw):
                msg = (
                    "Tavily API-ключ не задан — добавьте TAVILY_API_KEY в .env "
                    "или ключ в настройках панели, затем при необходимости: "
                    "docker compose up -d --force-recreate celery_worker backend"
                )
            else:
                msg = (
                    "Веб-поиск не вернул результатов — проверьте ключи Tavily "
                    "и месячные лимиты (в настройках можно добавить запасной ключ)"
                )
            raise RuntimeError(msg)

        context = ""
        for block in blocks:
            if len(context) + len(block) > _MAX_CONTEXT_CHARS:
                break
            context += block + "\n"
        return context.strip(), sources
