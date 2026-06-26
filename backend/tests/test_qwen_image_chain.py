"""Тесты цепочки моделей Qwen-Image."""

from app.infrastructure.ai.qwen_image_chain import (
    is_quota_exhausted,
    parse_model_chain,
    resolve_generate_models,
)


def test_parse_model_chain_from_commas() -> None:
    models = parse_model_chain(
        "qwen-image-plus, qwen-image-max\nqwen-image",
        fallback=("qwen-image-2.0",),
    )
    assert models == ["qwen-image-plus", "qwen-image-max", "qwen-image"]


def test_parse_model_chain_empty_uses_fallback() -> None:
    models = parse_model_chain("", fallback=("qwen-image-2.0",))
    assert models == ["qwen-image-2.0"]


def test_resolve_generate_models_prefers_env_single_model() -> None:
    models = resolve_generate_models("qwen-image-max,qwen-image-plus")
    assert models[0] == "qwen-image-max"


def test_quota_detection_403() -> None:
    assert is_quota_exhausted(status_code=403, body_text="")


def test_quota_detection_allocation_code() -> None:
    assert is_quota_exhausted(
        status_code=200,
        api_code="AllocationQuota.FreeTierOnly",
        message="Free quota exhausted",
    )
