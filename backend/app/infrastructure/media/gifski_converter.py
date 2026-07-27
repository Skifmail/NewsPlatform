"""Convert MP4 animation bytes to high-quality GIF via ffmpeg + gifski.

Uses the ImageOptim gifski CLI (https://github.com/ImageOptim/gifski) with
ffmpeg YUV4MPEG pipe input — the recommended high-quality path.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
import tempfile
from pathlib import Path

from loguru import logger

GIF_MAGIC = (b"GIF87a", b"GIF89a")

# Quality-first defaults: gifski otherwise caps ~800×600.
DEFAULT_GIF_QUALITY = 100
DEFAULT_GIF_WIDTH = 1024
DEFAULT_GIF_FPS = 20
_CONVERT_TIMEOUT_SECONDS = 180


def is_gif_bytes(data: bytes | None) -> bool:
    """Return True when *data* starts with a GIF signature."""
    if not data or len(data) < 6:
        return False
    return data[:6] in GIF_MAGIC


def gifski_available() -> bool:
    """Return True when both ffmpeg and gifski are on PATH."""
    return shutil.which("ffmpeg") is not None and shutil.which("gifski") is not None


def convert_mp4_to_gif_sync(
    video_bytes: bytes,
    *,
    quality: int = DEFAULT_GIF_QUALITY,
    width: int = DEFAULT_GIF_WIDTH,
    fps: int = DEFAULT_GIF_FPS,
    extra: bool = True,
) -> bytes:
    """Encode MP4 bytes to GIF using ffmpeg → gifski.

    Args:
        video_bytes: Source MP4 (or other ffmpeg-readable) container.
        quality: gifski ``--quality`` 1–100 (100 = maximum).
        width: Max output width in pixels (preserves aspect ratio).
        fps: Target frame rate for resampling.
        extra: Pass ``--extra`` for slightly better quality (slower).

    Returns:
        GIF file bytes.

    Raises:
        FileNotFoundError: ffmpeg or gifski missing.
        RuntimeError: conversion failed or produced empty/invalid output.
    """
    if not video_bytes:
        msg = "Empty video bytes"
        raise RuntimeError(msg)
    if shutil.which("ffmpeg") is None:
        raise FileNotFoundError("ffmpeg not found on PATH")
    if shutil.which("gifski") is None:
        raise FileNotFoundError("gifski not found on PATH")

    quality = max(1, min(100, int(quality)))
    width = max(64, min(4096, int(width)))
    fps = max(1, min(60, int(fps)))

    with tempfile.TemporaryDirectory(prefix="gifski_") as tmp:
        tmp_path = Path(tmp)
        inp = tmp_path / "in.mp4"
        out = tmp_path / "out.gif"
        inp.write_bytes(video_bytes)

        ffmpeg_cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(inp),
            "-f",
            "yuv4mpegpipe",
            "-",
        ]
        gifski_cmd = [
            "gifski",
            "--quiet",
            "--output",
            str(out),
            "--quality",
            str(quality),
            "--width",
            str(width),
            "--fps",
            str(fps),
            "--repeat",
            "0",
        ]
        if extra:
            gifski_cmd.append("--extra")
        gifski_cmd.append("-")

        logger.debug(
            "gifski convert start",
            quality=quality,
            width=width,
            fps=fps,
            input_kb=len(video_bytes) // 1024,
        )

        ffmpeg_proc = subprocess.Popen(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        assert ffmpeg_proc.stdout is not None
        try:
            gifski_proc = subprocess.run(
                gifski_cmd,
                stdin=ffmpeg_proc.stdout,
                capture_output=True,
                timeout=_CONVERT_TIMEOUT_SECONDS,
                check=False,
            )
        finally:
            ffmpeg_proc.stdout.close()
            try:
                ffmpeg_stderr = ffmpeg_proc.communicate(timeout=30)[1]
            except subprocess.TimeoutExpired:
                ffmpeg_proc.kill()
                ffmpeg_stderr = ffmpeg_proc.communicate()[1]

        if gifski_proc.returncode != 0 or not out.is_file() or out.stat().st_size == 0:
            err_parts = [
                gifski_proc.stderr.decode("utf-8", errors="replace").strip(),
                (ffmpeg_stderr or b"").decode("utf-8", errors="replace").strip(),
            ]
            detail = " | ".join(p for p in err_parts if p) or "unknown error"
            msg = f"gifski conversion failed: {detail}"
            raise RuntimeError(msg)

        gif_bytes = out.read_bytes()
        if not is_gif_bytes(gif_bytes):
            msg = "gifski output is not a valid GIF"
            raise RuntimeError(msg)

        logger.info(
            "gifski convert ok",
            input_kb=len(video_bytes) // 1024,
            output_kb=len(gif_bytes) // 1024,
            quality=quality,
            width=width,
        )
        return gif_bytes


async def convert_mp4_to_gif(
    video_bytes: bytes,
    *,
    quality: int = DEFAULT_GIF_QUALITY,
    width: int = DEFAULT_GIF_WIDTH,
    fps: int = DEFAULT_GIF_FPS,
    extra: bool = True,
) -> bytes:
    """Async wrapper around :func:`convert_mp4_to_gif_sync`."""
    return await asyncio.to_thread(
        convert_mp4_to_gif_sync,
        video_bytes,
        quality=quality,
        width=width,
        fps=fps,
        extra=extra,
    )
