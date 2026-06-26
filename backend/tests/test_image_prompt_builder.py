"""Тесты промптов обложек."""

from types import SimpleNamespace

from app.infrastructure.ai.image_prompt_builder import ImagePromptBuilder


def _channel(guidelines: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name="Test",
        topic="science",
        image_prompt_guidelines=guidelines,
    )


def test_railway_news_hint() -> None:
    hint = ImagePromptBuilder._visual_hint_from_title(
        "В Оренбургской области груженые щебнем вагоны сошли с рельсов"
    )
    assert "train" in hint.lower()
    assert "no people" in hint.lower()


def test_airport_news_hint() -> None:
    hint = ImagePromptBuilder._visual_hint_from_title(
        "Аэропорт Домодедово обслуживает рейсы по согласованию"
    )
    assert "airport" in hint.lower()


def test_gas_station_news_hint() -> None:
    hint = ImagePromptBuilder._visual_hint_from_title(
        "В Омской области вводят меры против спекуляции на АЗС"
    )
    assert "gas" in hint.lower() or "highway" in hint.lower()


def test_default_hint_avoids_portraits() -> None:
    hint = ImagePromptBuilder._visual_hint_from_title("Новое заявление чиновника")
    lowered = hint.lower()
    assert "no people" in lowered or "no portraits" in lowered
    assert "photojournalistic" not in lowered


def test_build_for_channel_requires_guidelines() -> None:
    assert ImagePromptBuilder.build_for_channel(_channel(), scene="moon surface") is None


def test_build_for_channel_uses_only_channel_template() -> None:
    template = "Landscape illustration, no text. Scene: {scene}."
    prompt = ImagePromptBuilder.build_for_channel(
        _channel(template),
        scene="tuning fork in space",
    )
    assert prompt == "Landscape illustration, no text. Scene: tuning fork in space."


def test_build_for_channel_strips_cyrillic_from_title() -> None:
    template = "Cover art. Scene: {scene}. Topic hint: {title}."
    prompt = ImagePromptBuilder.build_for_channel(
        _channel(template),
        scene="laboratory",
        title="Звук в вакууме: почему нет звука",
    )
    assert "Звук" not in prompt
    assert "вакууме" not in prompt


def test_sanitize_scene_removes_text_triggers() -> None:
    scene = ImagePromptBuilder._sanitize_scene_for_qwen(
        "science-pop illustration for curious adult audience with Russian text"
    )
    lowered = scene.lower()
    assert "science-pop" not in lowered
    assert "audience" not in lowered
    assert "russian" not in lowered
