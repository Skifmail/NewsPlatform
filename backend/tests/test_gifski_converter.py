"""Tests for gifski MP4→GIF conversion helpers."""

from unittest.mock import patch

from app.infrastructure.media.gifski_converter import is_gif_bytes


def test_is_gif_bytes_detects_signatures() -> None:
    assert is_gif_bytes(b"GIF89a" + b"\x00" * 10)
    assert is_gif_bytes(b"GIF87a" + b"\x00" * 10)
    assert not is_gif_bytes(b"\x00\x00\x00\x18ftyp")
    assert not is_gif_bytes(b"")
    assert not is_gif_bytes(None)


def test_gifski_available_requires_both_binaries() -> None:
    from app.infrastructure.media import gifski_converter as mod

    with patch.object(mod.shutil, "which", side_effect=lambda name: "/bin/x" if name == "ffmpeg" else None):
        assert mod.gifski_available() is False
    with patch.object(mod.shutil, "which", return_value="/bin/x"):
        assert mod.gifski_available() is True
