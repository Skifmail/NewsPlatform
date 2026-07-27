"""Tests for OpenRouter video client (silent generation request)."""

from app.infrastructure.ai.openrouter_video_client import (
    OpenRouterVideoClient,
    _ensure_silent_video_prompt,
)


def test_ensure_silent_video_prompt_appends_suffix() -> None:
    result = _ensure_silent_video_prompt("Animate the scene")
    assert "no audio" in result.lower()
    assert result.startswith("Animate the scene")


def test_ensure_silent_video_prompt_skips_when_already_silent() -> None:
    original = "Animate quietly, no audio track"
    assert _ensure_silent_video_prompt(original) == original


def test_animate_image_payload_disables_audio(monkeypatch) -> None:
    captured: dict = {}

    class FakeResponse:
        status_code = 200

        def json(self) -> dict:
            return {
                "id": "job-1",
                "status": "completed",
                "unsigned_urls": ["https://cdn.example.com/v.mp4"],
            }

        @property
        def content(self) -> bytes:
            return b"video-bytes"

        @property
        def headers(self) -> dict:
            return {"content-type": "video/mp4"}

        @property
        def text(self) -> str:
            return ""

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def post(self, url, headers=None, json=None):
            captured["json"] = json
            return FakeResponse()

        async def get(self, url, headers=None):
            return FakeResponse()

    monkeypatch.setattr(
        "app.infrastructure.ai.openrouter_video_client.httpx.AsyncClient",
        FakeClient,
    )

    import asyncio

    client = OpenRouterVideoClient(api_key="test-key")
    result = asyncio.run(
        client.animate_image(
            image_bytes=b"\x89PNG\r\n\x1a\n",
            prompt="Move clouds gently",
        )
    )

    assert result.video_bytes == b"video-bytes"
    payload = captured["json"]
    assert payload["generate_audio"] is False
    assert "no audio" in payload["prompt"].lower()
    assert payload["provider"]["options"]["x-ai"]["parameters"]["generate_audio"] is False
