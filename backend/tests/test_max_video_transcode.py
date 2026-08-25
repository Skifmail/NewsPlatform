"""Tests for MAX video prepare/transcode helper."""

from unittest.mock import patch

from app.infrastructure.media.max_video_transcode import (
    _MAX_BYTES_BEFORE_TRANSCODE,
    _TARGET_SIZE_RATIO,
    _target_video_bitrate,
    prepare_video_for_max,
)


def test_small_video_passed_through() -> None:
    payload = b"fake-mp4-bytes"
    with patch(
        "app.infrastructure.media.max_video_transcode._assert_readable"
    ):
        assert prepare_video_for_max(payload) is payload


def test_large_video_transcoded() -> None:
    payload = b"x" * (_MAX_BYTES_BEFORE_TRANSCODE + 1)
    with (
        patch(
            "app.infrastructure.media.max_video_transcode._assert_readable"
        ),
        patch(
            "app.infrastructure.media.max_video_transcode.shutil.which",
            return_value="/usr/bin/ffmpeg",
        ),
        patch(
            "app.infrastructure.media.max_video_transcode._transcode",
            return_value=b"small",
        ) as mock_t,
    ):
        assert prepare_video_for_max(payload) == b"small"
        mock_t.assert_called_once_with(payload)


def test_target_bitrate_aims_for_six_to_seven_x() -> None:
    # 199 МБ / 97 с → ~2.5 Мбит/с видео при ratio 6.5
    src = 199 * 1024 * 1024
    bps = _target_video_bitrate(src, 97.5)
    target_bytes = src / _TARGET_SIZE_RATIO
    expected_total = target_bytes * 8 / 97.5
    assert 1_800_000 <= bps <= 4_500_000
    assert abs(bps + 128_000 - expected_total) < 50_000
