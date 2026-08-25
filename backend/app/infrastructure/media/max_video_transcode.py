"""Подготовка видео для MAX: мягкое сжатие больших MP4 перед upload.

Callers: MaxPublisher._resolve_video_token.
Цель: ~6–7× меньше исходника (не 20–25×), чтобы MAX успевал
обработать ролик без сильной потери качества.
User: «сжимаешь в 24 раза… давай хотя бы в 6-7 раз».
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from loguru import logger

# Ниже порога — без перекодирования (открытки ~1–3 МБ).
_MAX_BYTES_BEFORE_TRANSCODE = 12 * 1024 * 1024
# Целевой коэффициент сжатия размера файла (~6–7×).
_TARGET_SIZE_RATIO = 6.5
_TARGET_HEIGHT = 1080
_AUDIO_BITRATE_K = 128
_MIN_VIDEO_BITRATE = 1_800_000  # ~1.8 Мбит/с
_MAX_VIDEO_BITRATE = 4_500_000  # ~4.5 Мбит/с


def prepare_video_for_max(video_bytes: bytes) -> bytes:
    """Возвращает байты, пригодные для upload в MAX (сжимает при необходимости).

    Args:
        video_bytes: исходный MP4/видеофайл.

    Returns:
        bytes: исходные или перекодированные байты.

    Raises:
        RuntimeError: файл битый или ffmpeg недоступен при необходимости сжатия.
    """
    if not video_bytes:
        return video_bytes

    _assert_readable(video_bytes)

    if len(video_bytes) <= _MAX_BYTES_BEFORE_TRANSCODE:
        return video_bytes

    if shutil.which("ffmpeg") is None:
        logger.warning(
            "ffmpeg missing; uploading original large video to MAX",
            size_mb=round(len(video_bytes) / (1024 * 1024), 1),
        )
        return video_bytes

    return _transcode(video_bytes)


def _assert_readable(video_bytes: bytes) -> None:
    """Падает рано, если контейнер без moov (обрезанная заливка)."""
    if shutil.which("ffprobe") is None:
        return
    with tempfile.NamedTemporaryFile(suffix=".mp4") as tmp:
        tmp.write(video_bytes)
        tmp.flush()
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                tmp.name,
            ],
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    if proc.returncode != 0 or not (proc.stdout or "").strip():
        err = (proc.stderr or "").strip()[:300]
        raise RuntimeError(
            "Видеофайл повреждён или загружен не полностью (нет moov atom). "
            f"Загрузите файл заново. {err}"
        )


def _probe_meta(path: Path) -> dict[str, float | int]:
    """Читает duration/height через ffprobe."""
    proc = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=height:format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if proc.returncode != 0:
        return {"duration": 0.0, "height": 0}
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        return {"duration": 0.0, "height": 0}
    duration = float((data.get("format") or {}).get("duration") or 0.0)
    streams = data.get("streams") or []
    height = int((streams[0] or {}).get("height") or 0) if streams else 0
    return {"duration": duration, "height": height}


def _target_video_bitrate(src_size: int, duration: float) -> int:
    """Битрейт видео под целевой размер ~src/_TARGET_SIZE_RATIO."""
    if duration <= 0:
        return 2_500_000
    target_bytes = src_size / _TARGET_SIZE_RATIO
    total_bps = int(target_bytes * 8 / duration)
    audio_bps = _AUDIO_BITRATE_K * 1000
    video_bps = total_bps - audio_bps
    return max(_MIN_VIDEO_BITRATE, min(_MAX_VIDEO_BITRATE, video_bps))


def _transcode(video_bytes: bytes) -> bytes:
    """H.264 до 1080p с битрейтом ~1/6.5 от исходного размера."""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "src.mp4"
        dst = Path(tmpdir) / "out.mp4"
        src.write_bytes(video_bytes)
        meta = _probe_meta(src)
        duration = float(meta["duration"])
        height = int(meta["height"])
        video_bps = _target_video_bitrate(len(video_bytes), duration)

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(src),
        ]
        # Даунскейл только если выше 1080; иначе сохраняем исходное разрешение.
        if height > _TARGET_HEIGHT:
            cmd.extend(["-vf", f"scale=-2:{_TARGET_HEIGHT}"])
        cmd.extend(
            [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-b:v",
                str(video_bps),
                "-maxrate",
                str(int(video_bps * 1.3)),
                "-bufsize",
                str(int(video_bps * 2)),
                "-c:a",
                "aac",
                "-b:a",
                f"{_AUDIO_BITRATE_K}k",
                "-movflags",
                "+faststart",
                str(dst),
            ]
        )
        logger.info(
            "MAX transcoding large video",
            src_mb=round(len(video_bytes) / (1024 * 1024), 1),
            height=height,
            target_height=min(height, _TARGET_HEIGHT) if height else _TARGET_HEIGHT,
            video_bitrate_kbps=round(video_bps / 1000),
            target_ratio=_TARGET_SIZE_RATIO,
        )
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if proc.returncode != 0 or not dst.is_file():
            raise RuntimeError(
                "Не удалось сжать видео для MAX: "
                + (proc.stderr or "")[-400:]
            )
        out = dst.read_bytes()
        ratio = (len(video_bytes) / len(out)) if out else 0.0
        logger.info(
            "MAX video transcoded",
            src_mb=round(len(video_bytes) / (1024 * 1024), 1),
            dst_mb=round(len(out) / (1024 * 1024), 1),
            ratio=round(ratio, 1),
        )
        return out
