"""Тесты усиленного дедупа тем: общий субъект и защита от ложных совпадений."""

from app.domain.topic_dedup import is_topic_too_similar
from app.domain.prompt_defaults import PROMPT_DEFAULTS


def test_bumblebee_near_duplicate_caught() -> None:
    """Разная формулировка одной темы (шмель+аэродинамика) ловится по субъекту."""
    a = "Шмель летает вопреки законам физики? Разоблачаем миф"
    b = "Шмель-нарушитель: как пушистый бомбардировщик обманул аэродинамику"
    assert is_topic_too_similar(a, [b]) is True


def test_same_subject_pyramids_caught() -> None:
    a = "Пирамиды Амазонии: почему мы о них не знали?"
    b = "Почему пирамиды стоят именно в Гизе: геология как архитектор"
    assert is_topic_too_similar(a, [b]) is True


def test_single_shared_distinctive_word_not_flagged() -> None:
    """Одно общее отличительное слово НЕ делает темы дубликатами (регресс 9098caf).

    Из-за срабатывания по одному слову идеация канала находок отвергала все
    варианты и падала «не удалось подобрать уникальную тему».
    """
    candidate = "Zed: быстрый редактор кода на Rust"
    recent = ["Helix: модальный редактор в терминале"]
    assert is_topic_too_similar(candidate, recent) is False


def test_two_shared_distinctive_words_flagged() -> None:
    """Два общих отличительных слова — уже дубликат."""
    candidate = "Zed: модальный редактор на Rust"
    recent = ["Helix: модальный редактор в терминале"]
    assert is_topic_too_similar(candidate, recent) is True


def test_shared_verb_not_flagged() -> None:
    """Общий глагол «падают» не делает разные темы дубликатами."""
    a = "Почему небоскребы не падают: крошечные ошибки в проекте"
    b = "Почему спутники не падают на Землю: секрет орбитальной скорости"
    assert is_topic_too_similar(a, [b]) is False


def test_shared_country_not_flagged() -> None:
    """Две разные темы про одну страну — не дубликаты (баланс делает промпт)."""
    a = "Почему в Японии до сих пор используют факсы и дискеты"
    b = "Почему в Японии левостороннее движение: самураи и рельсы"
    assert is_topic_too_similar(a, [b]) is False


def test_generic_filler_not_flagged() -> None:
    """Общий филлер (секрет/тайна/наука) не схлопывает разные темы."""
    a = "Тайна золотого сечения: секрет красоты"
    b = "Секрет римского бетона: тайна прочности"
    assert is_topic_too_similar(a, [b]) is False


def test_distinct_topics_stay_distinct() -> None:
    assert is_topic_too_similar(
        "Почему небо голубое", ["Почему трава зелёная"]
    ) is False
    assert is_topic_too_similar(
        "Как работает эхолокация летучих мышей", ["История Эйфелевой башни"]
    ) is False


def test_paragraph_prompt_has_balancing_rules() -> None:
    extra = PROMPT_DEFAULTS["ideation.paragraph_extra"].template_text
    assert "СУБЪЕКТ" in extra
    assert "ЗАГОЛОВОК" in extra
    assert "ошибка" in extra.lower() or "рубрик" in extra.lower()
