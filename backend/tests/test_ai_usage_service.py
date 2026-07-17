"""Тесты AiUsageService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.schemas.ai_usage import AiUsageResponse
from app.services.ai_usage_service import (
    AiUsageService,
    _build_chain_status,
    _fetch_deepseek,
    _fetch_tavily,
    _is_configured,
)


def test_is_configured_rejects_placeholders() -> None:
    assert _is_configured("") is False
    assert _is_configured("sk-...") is False
    assert _is_configured("sk-live-key") is True


def test_build_chain_status_marks_next_and_exhausted() -> None:
    chain = _build_chain_status(
        ["a", "b", "c"],
        [{"model": "a", "ttl_seconds": 120}],
    )
    assert chain[0].status == "exhausted"
    assert chain[1].status == "next"
    assert chain[2].status == "available"


@pytest.mark.asyncio
async def test_fetch_deepseek_parses_balance() -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "is_available": True,
        "balance_infos": [
            {
                "currency": "USD",
                "total_balance": "12.50",
                "granted_balance": "2.50",
                "topped_up_balance": "10.00",
            }
        ],
    }

    with patch("app.services.ai_usage_service.get_settings") as settings_mock:
        settings_mock.return_value = MagicMock(
            deepseek_api_key="sk-test",
            deepseek_api_base="https://api.deepseek.com",
            deepseek_model="deepseek-v4-pro",
            deepseek_fast_model="deepseek-chat",
        )
        with patch("app.services.ai_usage_service.httpx.AsyncClient") as client_cls:
            client = AsyncMock()
            client.__aenter__.return_value = client
            client.get = AsyncMock(return_value=response)
            client_cls.return_value = client

            usage = await _fetch_deepseek()

    assert usage.configured is True
    assert usage.total_balance == "12.50"
    assert usage.is_available is True


@pytest.mark.asyncio
async def test_fetch_tavily_parses_plan_usage() -> None:
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "key": {"usage": 150, "limit": 1000},
        "account": {
            "current_plan": "Researcher",
            "plan_usage": 150,
            "plan_limit": 1000,
            "search_usage": 120,
        },
    }
    session = AsyncMock()

    with patch("app.services.ai_usage_service.get_settings") as settings_mock:
        settings_mock.return_value = MagicMock(
            tavily_api_key="tvly-test",
            redis_url="redis://localhost:6379/0",
        )
        with patch(
            "app.services.ai_usage_service.PlatformSettingsService"
        ) as ps_cls:
            ps_cls.return_value.get_merged = AsyncMock(
                return_value={
                    "tavily_api_keys": "[]",
                    "tavily_active_key_id": "",
                    "tavily_auto_switch": "true",
                }
            )
            with patch(
                "app.services.ai_usage_service.list_exhausted_keys",
                return_value=[],
            ):
                with patch(
                    "app.services.ai_usage_service.httpx.AsyncClient"
                ) as client_cls:
                    client = AsyncMock()
                    client.__aenter__.return_value = client
                    client.get = AsyncMock(return_value=response)
                    client_cls.return_value = client

                    usage = await _fetch_tavily(session)

    assert usage.configured is True
    assert usage.current_plan == "Researcher"
    assert usage.remaining == 850
    assert len(usage.keys) == 1
    assert usage.keys[0].status == "next"


@pytest.mark.asyncio
async def test_get_usage_uses_cache() -> None:
    session = AsyncMock()
    cached = AiUsageResponse(
        fetched_at="2026-07-07T12:00:00+00:00",
        cache_ttl_seconds=600,
        from_cache=False,
        deepseek={"configured": True, "models": []},
        tavily={"configured": False},
        qwen_image={"configured": False, "note": ""},
        openai={"configured": False, "note": ""},
        local={},
    )

    service = AiUsageService(session)
    with patch.object(service, "_read_cache", return_value=cached):
        result = await service.get_usage(force_refresh=False)

    assert result.from_cache is True
    assert result.fetched_at == cached.fetched_at
