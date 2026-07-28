"""Tests for OpenRouter image client."""

import asyncio
import base64

from app.infrastructure.ai.openrouter_image_client import (
    OpenRouterImageClient,
    _SIZE_TO_ASPECT_RATIO,
)


def test_size_to_aspect_ratio_mapping() -> None:
    assert _SIZE_TO_ASPECT_RATIO["1024x1024"] == "1:1"
    assert _SIZE_TO_ASPECT_RATIO["1536x1024"] == "3:2"


def test_generate_posts_seedream_payload(monkeypatch) -> None:
    captured: dict = {}
    png_bytes = b"\x89PNG\r\n\x1a\nfake"
    b64 = base64.b64encode(png_bytes).decode("ascii")

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"data": [{"b64_json": b64}]}

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url, headers=None, json=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr(
        "app.infrastructure.ai.openrouter_image_client.httpx.AsyncClient",
        FakeClient,
    )

    client = OpenRouterImageClient(
        api_key="sk-or-test",
        model="bytedance-seed/seedream-4.5",
        resolution="2K",
    )
    result = asyncio.run(
        client.generate("A serene mountain landscape", size="1024x1024")
    )

    assert result is not None
    assert result.image_bytes == png_bytes
    assert captured["url"] == "https://openrouter.ai/api/v1/images"
    assert captured["headers"]["Authorization"] == "Bearer sk-or-test"
    payload = captured["json"]
    assert payload["model"] == "bytedance-seed/seedream-4.5"
    assert payload["aspect_ratio"] == "1:1"
    assert payload["resolution"] == "2K"


def test_generate_returns_none_without_key() -> None:
    client = OpenRouterImageClient(api_key="")
    result = asyncio.run(client.generate("test prompt"))
    assert result is None
