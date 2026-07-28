"""Tests for openai_image_quality platform setting."""

from app.domain.platform_settings import normalize_openai_image_quality


def test_normalize_openai_image_quality_accepts_valid_values() -> None:
    assert normalize_openai_image_quality("medium") == "medium"
    assert normalize_openai_image_quality("HIGH") == "high"
    assert normalize_openai_image_quality("auto") == "auto"


def test_normalize_openai_image_quality_falls_back_to_default() -> None:
    assert normalize_openai_image_quality("invalid") == "high"
    assert normalize_openai_image_quality("", default="medium") == "medium"
