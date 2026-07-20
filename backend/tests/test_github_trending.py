"""Тесты клиента GitHub Trending и идеации по живым кандидатам."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.infrastructure.ai.topic_ideation import _devtools_ideation_extra
from app.infrastructure.search.github_trending_client import (
    GitHubTrendingClient,
    TrendingRepo,
    _parse_item,
)


def _repo_item(full_name: str, stars: int, lang: str = "Python") -> dict:
    """Собирает элемент ответа Search API."""
    return {
        "full_name": full_name,
        "html_url": f"https://github.com/{full_name}",
        "description": f"desc of {full_name}",
        "stargazers_count": stars,
        "language": lang,
        "created_at": "2026-07-01T00:00:00Z",
        "pushed_at": "2026-07-19T00:00:00Z",
    }


def test_parse_item_valid() -> None:
    repo = _parse_item(_repo_item("owner/repo", 1234))
    assert repo is not None
    assert repo.full_name == "owner/repo"
    assert repo.stars == 1234
    assert repo.url == "https://github.com/owner/repo"


def test_parse_item_missing_fields() -> None:
    assert _parse_item({"description": "x"}) is None
    assert _parse_item("not a dict") is None


def test_candidate_line_truncates_long_description() -> None:
    repo = TrendingRepo(
        full_name="a/b",
        description="x" * 500,
        stars=10,
        language="Rust",
        url="https://github.com/a/b",
        created_at="",
        pushed_at="",
    )
    line = repo.as_candidate_line()
    assert line.startswith("a/b — ⭐10, Rust — ")
    assert "…" in line
    assert len(line) < 220


@pytest.mark.asyncio
async def test_fetch_trending_merges_and_ranks() -> None:
    """Объединяет два запроса, дедупит по имени и сортирует по звёздам."""
    rising = MagicMock()
    rising.status_code = 200
    rising.json.return_value = {
        "items": [_repo_item("new/hot", 800), _repo_item("dup/repo", 600)]
    }
    rising.raise_for_status = MagicMock()

    active = MagicMock()
    active.status_code = 200
    active.json.return_value = {
        "items": [_repo_item("big/popular", 90000), _repo_item("dup/repo", 600)]
    }
    active.raise_for_status = MagicMock()

    with patch(
        "app.infrastructure.search.github_trending_client.httpx.AsyncClient"
    ) as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get = AsyncMock(side_effect=[rising, active])
        client_cls.return_value = client

        repos = await GitHubTrendingClient(token="").fetch_trending(limit=10)

    names = [r.full_name for r in repos]
    assert names == ["big/popular", "new/hot", "dup/repo"]  # по убыванию звёзд, без дублей


@pytest.mark.asyncio
async def test_fetch_trending_returns_empty_on_error() -> None:
    """Любая ошибка сети → пустой список (fallback идеации)."""
    with patch(
        "app.infrastructure.search.github_trending_client.httpx.AsyncClient"
    ) as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get = AsyncMock(side_effect=httpx.ConnectError("boom"))
        client_cls.return_value = client

        repos = await GitHubTrendingClient(token="").fetch_trending()

    assert repos == []


@pytest.mark.asyncio
async def test_fetch_trending_handles_rate_limit() -> None:
    """403 от API не роняет процесс, просто пустой результат по запросу."""
    limited = MagicMock()
    limited.status_code = 403
    limited.headers = {"x-ratelimit-remaining": "0"}

    with patch(
        "app.infrastructure.search.github_trending_client.httpx.AsyncClient"
    ) as client_cls:
        client = AsyncMock()
        client.__aenter__.return_value = client
        client.get = AsyncMock(return_value=limited)
        client_cls.return_value = client

        repos = await GitHubTrendingClient(token="tok").fetch_trending()

    assert repos == []


def test_devtools_extra_with_candidates_forces_choice() -> None:
    extra = _devtools_ideation_extra(["owner/repo — ⭐9000, Go — desc (url)"])
    assert "ЖИВОЙ список" in extra
    assert "owner/repo" in extra
    assert "Выбери РОВНО ОДИН" in extra


def test_devtools_extra_without_candidates_falls_back() -> None:
    extra = _devtools_ideation_extra(None)
    assert "ЖИВОЙ список" not in extra
    assert "search_queries" in extra
