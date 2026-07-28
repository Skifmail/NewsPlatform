"""Тесты AiUsageService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.schemas.ai_usage import AiUsageResponse
from app.services.ai_usage_service import (
    AiUsageService,
    _aggregate_openai_cost_buckets,
    _build_chain_status,
    _fetch_deepseek,
    _fetch_openai,
    _fetch_openrouter,
    _fetch_tavily,
    _is_configured,
    _sum_openai_spend_for_days,
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
async def test_fetch_openrouter_parses_credits_and_key() -> None:
    key_resp = MagicMock()
    key_resp.status_code = 200
    key_resp.json.return_value = {
        "data": {
            "label": "prod",
            "usage": 1.25,
            "usage_daily": 0.1,
            "usage_monthly": 0.8,
            "limit": None,
            "limit_remaining": None,
            "is_free_tier": False,
        }
    }
    credits_resp = MagicMock()
    credits_resp.status_code = 200
    credits_resp.json.return_value = {
        "data": {"total_credits": 50.0, "total_usage": 12.5},
    }
    session = AsyncMock()

    with patch("app.services.ai_usage_service.get_settings") as settings_mock:
        settings_mock.return_value = MagicMock(openrouter_api_key="")
        with patch(
            "app.services.ai_usage_service.PlatformSettingsService"
        ) as ps_cls:
            ps_cls.return_value.get_merged = AsyncMock(
                return_value={
                    "openrouter_api_keys": (
                        '[{"id":"1","label":"prod","key":"sk-or-v1-test",'
                        '"enabled":true}]'
                    ),
                    "openrouter_api_key": "",
                }
            )
            with patch(
                "app.services.ai_usage_service.httpx.AsyncClient"
            ) as client_cls:
                client = AsyncMock()
                client.__aenter__.return_value = client
                client.get = AsyncMock(side_effect=[key_resp, credits_resp])
                client_cls.return_value = client

                usage = await _fetch_openrouter(session)

    assert usage.configured is True
    assert usage.remaining == 37.5
    assert usage.total_credits == 50.0
    assert usage.key_usage == 1.25
    assert usage.key_label == "prod"


def test_aggregate_openai_cost_buckets_sums_daily_and_line_items() -> None:
    buckets = [
        {
            "start_time_iso": "2026-07-27T00:00:00+00:00",
            "results": [
                {
                    "line_item": "gpt-image-2 image, output",
                    "amount": {"value": "1.5", "currency": "usd"},
                    "quantity": 10.0,
                },
                {
                    "line_item": "gpt-image-2 text, input",
                    "amount": {"value": "0.25", "currency": "usd"},
                    "quantity": 100.0,
                },
            ],
        },
        {
            "start_time_iso": "2026-07-28T00:00:00+00:00",
            "results": [
                {
                    "line_item": "gpt-image-2 image, output",
                    "amount": {"value": "2.0", "currency": "usd"},
                    "quantity": 5.0,
                },
            ],
        },
    ]

    total, currency, daily, line_items = _aggregate_openai_cost_buckets(buckets)

    assert total == 3.75
    assert currency == "USD"
    assert len(daily) == 2
    assert line_items["gpt-image-2 image, output"] == (3.5, 15.0)
    assert _sum_openai_spend_for_days(daily, 1) == 2.0
    assert _sum_openai_spend_for_days(daily, 7) == 3.75


@pytest.mark.asyncio
async def test_fetch_openai_uses_admin_key_for_billing() -> None:
    costs_resp = MagicMock()
    costs_resp.status_code = 200
    costs_resp.json.return_value = {
        "data": [
            {
                "start_time_iso": "2026-07-28T00:00:00+00:00",
                "results": [
                    {
                        "line_item": "gpt-image-2 image, output",
                        "amount": {"value": "6.97", "currency": "usd"},
                        "quantity": 100.0,
                    },
                ],
            },
        ],
        "has_more": False,
    }
    images_resp = MagicMock()
    images_resp.status_code = 200
    images_resp.json.return_value = {"data": [], "has_more": False}
    limit_resp = MagicMock()
    limit_resp.status_code = 404
    session = AsyncMock()

    with patch("app.services.ai_usage_service.get_settings") as settings_mock:
        settings_mock.return_value = MagicMock(
            openai_api_key="sk-proj-test",
            openai_admin_api_key="sk-admin-test",
        )
        with patch(
            "app.services.ai_usage_service.PlatformSettingsService"
        ) as ps_cls:
            ps_cls.return_value.get_merged = AsyncMock(
                return_value={"openai_api_keys": "[]"},
            )
            with patch(
                "app.services.ai_usage_service.httpx.AsyncClient"
            ) as client_cls:
                client = AsyncMock()
                client.__aenter__.return_value = client
                client.get = AsyncMock(
                    side_effect=[costs_resp, images_resp, limit_resp],
                )
                client_cls.return_value = client

                usage = await _fetch_openai(session)

    assert usage.configured is True
    assert usage.billing_available is True
    assert usage.total_spent_30d == 6.97
    assert usage.line_items_30d[0].line_item == "gpt-image-2 image, output"


@pytest.mark.asyncio
async def test_fetch_openai_prompts_for_admin_key() -> None:
    session = AsyncMock()

    with patch("app.services.ai_usage_service.get_settings") as settings_mock:
        settings_mock.return_value = MagicMock(
            openai_api_key="sk-proj-test",
            openai_admin_api_key="",
        )
        with patch(
            "app.services.ai_usage_service.PlatformSettingsService"
        ) as ps_cls:
            ps_cls.return_value.get_merged = AsyncMock(
                return_value={"openai_api_keys": "[]"},
            )

            usage = await _fetch_openai(session)

    assert usage.configured is True
    assert usage.billing_available is False
    assert "OPENAI_ADMIN_API_KEY" in (usage.note or "")


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
        openrouter={"configured": False, "note": ""},
        local={},
    )

    service = AiUsageService(session)
    with patch.object(service, "_read_cache", return_value=cached):
        result = await service.get_usage(force_refresh=False)

    assert result.from_cache is True
    assert result.fetched_at == cached.fetched_at
