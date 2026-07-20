"""Клиент живого GitHub Trending через официальный Search API.

GitHub не отдаёт «trending» отдельным API, поэтому список горячих
репозиториев приближается двумя запросами к Search API:
- «взлетающие»: свежесозданные репозитории с большим числом звёзд;
- «популярные и живые»: крупные репозитории с недавним пушем.

Результаты объединяются и сортируются по звёздам. При любой ошибке
возвращается пустой список — идеация тогда откатывается на выбор темы
«из памяти» модели, как раньше.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
from loguru import logger

from app.core.config import get_settings

_API_URL = "https://api.github.com/search/repositories"
_TIMEOUT = 20.0
_USER_AGENT = "Mozilla/5.0 (compatible; NewsPlatform/1.0)"
_PER_PAGE = 30


@dataclass(frozen=True)
class TrendingRepo:
    """Один репозиторий из GitHub Trending."""

    full_name: str
    description: str
    stars: int
    language: str
    url: str
    created_at: str
    pushed_at: str

    def heat(self, now: datetime | None = None) -> float:
        """«Горячесть» = звёзды в день с момента создания.

        Приближает скорость набора звёзд, которой Search API не отдаёт:
        свежий репозиторий с тысячами звёзд обгоняет вечнозелёный
        мегасписок, набравший их за годы.

        Args:
            now: текущий момент (для тестируемости).

        Returns:
            float: оценка «горячести», больше — актуальнее.
        """
        moment = now or datetime.now(UTC)
        try:
            created = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError:
            return float(self.stars)
        age_days = max((moment - created).days, 14)
        return self.stars / age_days

    def as_candidate_line(self) -> str:
        """Строка репозитория для промпта идеации.

        Returns:
            str: «owner/repo — ⭐N, lang — описание (url)».
        """
        desc = self.description.strip() or "без описания"
        if len(desc) > 160:
            desc = f"{desc[:157]}…"
        lang = self.language or "n/a"
        return f"{self.full_name} — ⭐{self.stars}, {lang} — {desc} ({self.url})"


class GitHubTrendingClient:
    """Асинхронный клиент выборки трендовых репозиториев GitHub."""

    def __init__(self, token: str | None = None) -> None:
        self._token = (token if token is not None else get_settings().github_token).strip()

    def _headers(self) -> dict[str, str]:
        """Заголовки запроса с опциональной авторизацией.

        Returns:
            dict[str, str]: заголовки для GitHub API.
        """
        headers = {
            "User-Agent": _USER_AGENT,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    async def fetch_trending(
        self,
        *,
        languages: list[str] | None = None,
        limit: int = 30,
        rising_days: int = 180,
        active_days: int = 21,
        max_age_days: int = 730,
        min_stars_rising: int = 500,
        min_stars_active: int = 1500,
        max_stars_active: int = 90000,
    ) -> list[TrendingRepo]:
        """Возвращает объединённый список трендовых репозиториев.

        Args:
            languages: фильтр по языкам (напр. ["python", "rust"]); None — любые.
            limit: максимум репозиториев в итоге.
            rising_days: окно «свежести» для взлетающих репозиториев.
            active_days: окно недавнего пуша для активных репозиториев.
            max_age_days: не старше стольки дней для активной выборки — чтобы
                не тащить вечнозелёные мегасписки (awesome, build-your-own-x).
            min_stars_rising: порог звёзд для взлетающих.
            min_stars_active: нижний порог звёзд для активных.
            max_stars_active: верхний порог звёзд для активных (отсекает гигантов).

        Returns:
            list[TrendingRepo]: репозитории по убыванию «горячести», без дублей.
        """
        now = datetime.now(UTC)
        rising_since = (now - timedelta(days=rising_days)).date().isoformat()
        active_since = (now - timedelta(days=active_days)).date().isoformat()
        created_after = (now - timedelta(days=max_age_days)).date().isoformat()
        lang_filter = ""
        if languages:
            lang_filter = " " + " ".join(f"language:{lang}" for lang in languages[:1])

        queries = [
            f"stars:>{min_stars_rising} created:>{rising_since}{lang_filter}",
            (
                f"stars:{min_stars_active}..{max_stars_active} "
                f"pushed:>{active_since} created:>{created_after}{lang_filter}"
            ),
        ]

        merged: dict[str, TrendingRepo] = {}
        try:
            async with httpx.AsyncClient(
                timeout=_TIMEOUT, headers=self._headers()
            ) as client:
                for query in queries:
                    repos = await self._search(client, query)
                    for repo in repos:
                        merged.setdefault(repo.full_name.lower(), repo)
        except Exception as exc:  # noqa: BLE001 — best-effort источник
            logger.warning("GitHub trending fetch failed", error=str(exc))
            return []

        ranked = sorted(merged.values(), key=lambda r: r.heat(now), reverse=True)
        logger.info(
            "GitHub trending fetched",
            total=len(ranked),
            authenticated=bool(self._token),
        )
        return ranked[:limit]

    async def _search(
        self, client: httpx.AsyncClient, query: str
    ) -> list[TrendingRepo]:
        """Один запрос к Search API.

        Args:
            client: открытый httpx-клиент.
            query: строка запроса GitHub Search.

        Returns:
            list[TrendingRepo]: распознанные репозитории.
        """
        response = await client.get(
            _API_URL,
            params={
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": _PER_PAGE,
            },
        )
        if response.status_code == 403:
            logger.warning(
                "GitHub trending rate-limited",
                remaining=response.headers.get("x-ratelimit-remaining"),
            )
            return []
        response.raise_for_status()
        payload = response.json()
        items = payload.get("items", []) if isinstance(payload, dict) else []
        return [parsed for item in items if (parsed := _parse_item(item))]


def _parse_item(item: object) -> TrendingRepo | None:
    """Преобразует элемент ответа Search API в TrendingRepo.

    Args:
        item: словарь одного репозитория из ответа GitHub.

    Returns:
        TrendingRepo | None: распознанный репозиторий или None.
    """
    if not isinstance(item, dict):
        return None
    full_name = str(item.get("full_name") or "").strip()
    url = str(item.get("html_url") or "").strip()
    if not full_name or not url:
        return None
    return TrendingRepo(
        full_name=full_name,
        description=str(item.get("description") or "").strip(),
        stars=int(item.get("stargazers_count") or 0),
        language=str(item.get("language") or "").strip(),
        url=url,
        created_at=str(item.get("created_at") or "").strip(),
        pushed_at=str(item.get("pushed_at") or "").strip(),
    )
