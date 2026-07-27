"""OpenRouter image-to-video client (xAI Grok Imagine Video)."""

from __future__ import annotations

import asyncio
import base64
import mimetypes
from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

from app.services.pipeline_emitter import begin_step, complete_step, fail_step
from app.services.pipeline_progress import truncate_text

_OPENROUTER_VIDEOS_URL = "https://openrouter.ai/api/v1/videos"
_DEFAULT_MODEL = "x-ai/grok-imagine-video"
_POLL_INTERVAL_SECONDS = 5.0
_MAX_POLL_ATTEMPTS = 120  # ~10 minutes
_SILENT_VIDEO_SUFFIX = (
    " Silent video only: no audio track, no sound effects, no music, no dialogue."
)


@dataclass(frozen=True)
class OpenRouterVideoResult:
    """Completed video generation job."""

    job_id: str
    video_bytes: bytes
    content_type: str


class OpenRouterVideoClient:
    """Submit image-to-video jobs and poll until completion."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = _DEFAULT_MODEL,
        timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key.strip()
        self._model = model.strip() or _DEFAULT_MODEL
        self._timeout = timeout

    async def animate_image(
        self,
        *,
        image_bytes: bytes,
        prompt: str,
        duration: int = 2,
        resolution: str = "480p",
        aspect_ratio: str = "1:1",
        generate_audio: bool = False,
    ) -> OpenRouterVideoResult:
        """Animate a still image with subtle motion guided by ``prompt``.

        Args:
            image_bytes: PNG/JPEG bytes of the postcard frame.
            prompt: Motion instructions; text on image should stay static.
            duration: Clip length in seconds (model-dependent).
            resolution: Output resolution (480p/720p/1080p).
            aspect_ratio: Square ``1:1`` so MAX/Telegram don't crop top/bottom.
            generate_audio: Ignored; requests are always sent with audio disabled.

        Returns:
            OpenRouterVideoResult: downloaded MP4 bytes.

        Raises:
            RuntimeError: on API or polling failure.
        """
        if generate_audio:
            logger.warning(
                "OpenRouter video: generate_audio=True ignored; platform disables audio"
            )
        if not self._api_key:
            msg = "OpenRouter API key is not configured"
            raise RuntimeError(msg)
        if not image_bytes:
            msg = "Image bytes are required for animation"
            raise RuntimeError(msg)

        mime = _guess_mime(image_bytes)
        data_url = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        silent_prompt = _ensure_silent_video_prompt(prompt)
        payload: dict[str, Any] = {
            "model": self._model,
            "prompt": silent_prompt[:2000],
            "duration": duration,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "generate_audio": False,
            "frame_images": [
                {
                    "type": "image_url",
                    "image_url": {"url": data_url},
                    "frame_type": "first_frame",
                }
            ],
        }
        if self._model.startswith("x-ai/"):
            payload["provider"] = {
                "options": {
                    "x-ai": {
                        "parameters": {
                            "generate_audio": False,
                        }
                    }
                }
            }

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://newsplatform.local",
            "X-Title": "NewsPlatform",
        }

        logger.debug(
            "OpenRouter video submit",
            model=self._model,
            generate_audio=False,
            duration=duration,
            resolution=resolution,
        )

        event_id = begin_step(
            label=f"OpenRouter → {self._model}",
            from_node="platform",
            to_node="openrouter",
            provider="OpenRouter",
            model=self._model,
            request_summary=truncate_text(
                f"image-to-video | {duration}s {resolution} | {silent_prompt}",
                480,
            ),
            progress=88,
            metadata={"duration": duration, "resolution": resolution},
        )

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                submit = await client.post(_OPENROUTER_VIDEOS_URL, headers=headers, json=payload)
                if submit.status_code >= 400:
                    msg = f"OpenRouter video submit failed: {submit.status_code} {submit.text}"
                    fail_step(event_id, msg)
                    raise RuntimeError(msg)
                job = submit.json()
                job_id = str(job.get("id") or "")
                polling_url = job.get("polling_url")
                if not job_id and not polling_url:
                    msg = f"OpenRouter video: unexpected submit response: {job}"
                    fail_step(event_id, msg)
                    raise RuntimeError(msg)

                status_data = await self._poll_job(client, headers, job, job_id=job_id)
                video_bytes, content_type = await self._download_video(client, headers, status_data)
                usage = status_data.get("usage")
                complete_step(
                    event_id,
                    response_summary=f"MP4 {len(video_bytes) // 1024} KB, job {job_id}",
                    metadata={"usage": usage, "job_id": job_id},
                )
                if usage:
                    logger.info("OpenRouter video usage", job_id=job_id, usage=usage)
                return OpenRouterVideoResult(
                    job_id=job_id or str(status_data.get("id") or ""),
                    video_bytes=video_bytes,
                    content_type=content_type,
                )
        except RuntimeError:
            raise
        except Exception as exc:
            fail_step(event_id, str(exc))
            raise

    async def _poll_job(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        initial: dict[str, Any],
        *,
        job_id: str,
    ) -> dict[str, Any]:
        current = initial
        for attempt in range(1, _MAX_POLL_ATTEMPTS + 1):
            status = str(current.get("status") or "").lower()
            logger.debug(
                "OpenRouter video poll",
                job_id=job_id,
                attempt=attempt,
                status=status,
            )
            if status == "completed":
                return current
            if status == "failed":
                err = current.get("error") or "Video generation failed"
                raise RuntimeError(str(err))
            if status in {"cancelled", "expired"}:
                err = current.get("error") or f"Video generation {status}"
                raise RuntimeError(str(err))

            polling_url = current.get("polling_url") or initial.get("polling_url")
            if not polling_url:
                if job_id:
                    polling_url = f"{_OPENROUTER_VIDEOS_URL}/{job_id}"
                else:
                    raise RuntimeError("OpenRouter video job missing polling_url")

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            poll = await client.get(polling_url, headers=headers)
            if poll.status_code >= 400:
                msg = f"OpenRouter video poll failed: {poll.status_code} {poll.text}"
                raise RuntimeError(msg)
            current = poll.json()
        msg = f"OpenRouter video timed out after {_MAX_POLL_ATTEMPTS} polls"
        raise RuntimeError(msg)

    async def _download_video(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        status_data: dict[str, Any],
    ) -> tuple[bytes, str]:
        urls = status_data.get("unsigned_urls") or []
        job_id = str(status_data.get("id") or "")
        candidates = list(urls)
        if job_id:
            candidates.append(
                f"https://openrouter.ai/api/v1/videos/{job_id}/content?index=0"
            )
        if not candidates:
            msg = f"OpenRouter video completed without download URLs: {status_data}"
            raise RuntimeError(msg)

        last_error = ""
        for url in candidates:
            req_headers = headers if str(url).startswith("https://openrouter.ai/api/") else None
            try:
                resp = await client.get(url, headers=req_headers)
                if resp.status_code >= 400:
                    last_error = f"{resp.status_code} {resp.text[:200]}"
                    continue
                content_type = resp.headers.get("content-type", "video/mp4")
                return resp.content, content_type
            except Exception as exc:
                last_error = str(exc)
        msg = f"Failed to download OpenRouter video: {last_error}"
        raise RuntimeError(msg)


def _ensure_silent_video_prompt(prompt: str) -> str:
    """Ask explicitly for a silent clip in the motion prompt."""
    cleaned = (prompt or "").strip()
    lowered = cleaned.lower()
    if "no audio" in lowered or "без звука" in lowered or "silent video" in lowered:
        return cleaned
    return f"{cleaned}{_SILENT_VIDEO_SUFFIX}"


def _guess_mime(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\x89PNG"):
        return "image/png"
    if image_bytes.startswith(b"\xff\xd8"):
        return "image/jpeg"
    guessed, _ = mimetypes.guess_type("frame.png")
    return guessed or "image/png"
