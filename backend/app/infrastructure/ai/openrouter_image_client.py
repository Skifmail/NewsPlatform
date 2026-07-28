"""OpenRouter image generation client (Seedream and compatible models)."""

from __future__ import annotations

import base64
from dataclasses import dataclass

import httpx
from loguru import logger

_OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"
_DEFAULT_MODEL = "bytedance-seed/seedream-4.5"
_DEFAULT_RESOLUTION = "2K"
_REQUEST_TIMEOUT_SECONDS = 420.0

_SIZE_TO_ASPECT_RATIO: dict[str, str] = {
    "1024x1024": "1:1",
    "1536x1024": "3:2",
    "1024x1536": "2:3",
    "1792x1024": "16:9",
    "1024x1792": "9:16",
}

# Seedream 4.5 rejects 2K for non-square ratios (e.g. 3:2 → 2048×1366 < min pixels).


def _effective_resolution(aspect_ratio: str, resolution: str) -> str:
    """Bump resolution for wide/tall ratios that fall below Seedream minimum at 2K."""
    normalized = (resolution or _DEFAULT_RESOLUTION).strip().upper()
    if aspect_ratio == "1:1":
        return normalized
    if normalized in {"1K", "2K"}:
        return "4K"
    return normalized


@dataclass(frozen=True)
class OpenRouterImageResult:
    """Completed image generation response."""

    image_bytes: bytes
    content_type: str


class OpenRouterImageClient:
    """Generate still images via OpenRouter's dedicated Image API."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        resolution: str = _DEFAULT_RESOLUTION,
        timeout: float = _REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip() or _DEFAULT_MODEL
        self._resolution = resolution.strip() or _DEFAULT_RESOLUTION
        self._timeout = timeout

    async def generate(
        self,
        prompt: str,
        *,
        size: str = "1024x1024",
        n: int = 1,
    ) -> OpenRouterImageResult | None:
        """Generate an image from a text prompt.

        Args:
            prompt: Scene description.
            size: Legacy OpenAI-style size hint mapped to Seedream aspect_ratio.
            n: Number of images (first result is returned).

        Returns:
            OpenRouterImageResult or None on failure.
        """
        if not self._api_key:
            logger.warning("OpenRouter image: API key is not configured")
            return None
        text = prompt.strip()
        if not text:
            return None

        aspect_ratio = _SIZE_TO_ASPECT_RATIO.get(size, "auto")
        resolution = _effective_resolution(aspect_ratio, self._resolution)
        payload = {
            "model": self._model,
            "prompt": text,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    _OPENROUTER_IMAGES_URL,
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:500] if exc.response is not None else ""
            logger.error(
                "OpenRouter image generation failed: {err} | response={detail}",
                err=str(exc),
                detail=detail,
                error_type=type(exc).__name__,
                model=self._model,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            )
            return None
        except Exception as exc:
            logger.error(
                "OpenRouter image generation failed: {err}",
                err=str(exc),
                error_type=type(exc).__name__,
                model=self._model,
                aspect_ratio=aspect_ratio,
                resolution=resolution,
            )
            return None

        data = body.get("data") or []
        if not data:
            logger.warning("OpenRouter image: empty data array", model=self._model)
            return None

        first = data[0]
        b64 = first.get("b64_json")
        if not b64:
            logger.warning("OpenRouter image: missing b64_json", model=self._model)
            return None

        try:
            image_bytes = base64.b64decode(b64, validate=True)
        except Exception as exc:
            logger.error("OpenRouter image: invalid base64", error=str(exc))
            return None

        return OpenRouterImageResult(image_bytes=image_bytes, content_type="image/png")
