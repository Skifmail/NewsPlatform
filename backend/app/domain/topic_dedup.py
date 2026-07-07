"""Дедупликация тем статей: семантические маркеры и проверка похожести."""

import re
from typing import Final

# (маркеры в тексте, канонический id концепции)
_CONCEPT_MARKERS: Final[list[tuple[tuple[str, ...], str]]] = [
    (("плацебо", "placebo", "сахарн", "таблетк", "пилюл"), "placebo"),
    (("дежавю", "дежа вю", "déjà", "deja vu", "deja-vu"), "deja_vu"),
    (("свидетел", "bystander", "дженовез", "kitty genovese"), "bystander"),
    (("ложн", "воспоминан", "false memor", "ненадёжн рассказчик"), "false_memory"),
    (("синестез", "synesthesia"), "synesthesia"),
    (("иллюз", "illusion", "дорисовыва", "обман зрен"), "optical_illusion"),
    (("сон", "снов", "dream", "кинотеатр"), "dreams"),
    (("зев", "yawn"), "yawning"),
    (("эхолокац", "echolocat", "видеть ушам"), "echolocation"),
    (("голуб", "pigeon", "магниторецеп", "компас"), "animal_navigation"),
    (("гравитац", "gravity", "невесомост"), "gravity"),
    (("парадокс", "paradox"), "paradox"),
    (("стресс", "кортизол", "stress"), "stress"),
    (("привычк", "habit", "дофамин"), "habits"),
    (("миф", "заблужден", "misconception"), "myths"),
    (("фламинго", "flamingo", "caroten", "carotin", "астаксантин"), "flamingo"),
    (("литопс", "lithops", "живые камни"), "lithops"),
    (("аксолotl", "axolotl"), "axolotl"),
    (("осьминог", "octopus"), "octopus"),
    (("пингвин", "penguin"), "penguin"),
    (("кит", "whale", "синий кит"), "whale"),
    (("муравь", "ant colony", "муравейник"), "ants"),
    (("бамбук", "bamboo"), "bamboo"),
    (("aurora", "полярн", "северное сияние"), "aurora"),
]

# Значимые «якорные» слова: одно совпадение = та же тема (перефраз заголовка).
_RARE_SUBJECT_WORDS: Final[frozenset[str]] = frozenset(
    {
        "фламинго",
        "flamingo",
        "литопс",
        "lithops",
        "аксолotl",
        "axolotl",
        "осьминог",
        "octopus",
        "плацебо",
        "placebo",
        "дежавю",
        "synesthesia",
        "синестезия",
        "penguin",
        "пингвин",
    }
)

_STOP_WORDS: Final[frozenset[str]] = frozenset(
    {
        "как",
        "что",
        "почему",
        "зачем",
        "когда",
        "где",
        "это",
        "для",
        "или",
        "при",
        "над",
        "под",
        "the",
        "and",
        "for",
        "with",
        "работает",
        "эффект",
        "effect",
    }
)


def extract_concepts(text: str) -> set[str]:
    """Извлекает канонические id концепций из названия темы или заголовка.

    Args:
        text: тема, заголовок или угол подачи.

    Returns:
        set[str]: набор id концепций.
    """
    lowered = _normalize(text)
    concepts: set[str] = set()
    for markers, concept_id in _CONCEPT_MARKERS:
        if any(marker in lowered for marker in markers):
            concepts.add(concept_id)
    return concepts


def is_topic_too_similar(candidate: str, recent: list[str]) -> bool:
    """Проверяет, слишком ли похожа тема на недавние.

    Сравнивает семантические концепции и значимые слова.

    Args:
        candidate: предлагаемая тема.
        recent: недавние темы и заголовки.

    Returns:
        bool: True если тему нужно отклонить.
    """
    if not candidate.strip() or not recent:
        return False

    candidate_norm = _normalize(candidate)
    candidate_concepts = extract_concepts(candidate)

    for prev in recent:
        prev_norm = _normalize(prev)
        if not prev_norm:
            continue
        if candidate_norm == prev_norm:
            return True
        if len(candidate_norm) >= 8 and (
            candidate_norm in prev_norm or prev_norm in candidate_norm
        ):
            return True

        prev_concepts = extract_concepts(prev)
        if candidate_concepts and prev_concepts and candidate_concepts & prev_concepts:
            return True

        shared_rare = _shared_rare_words(candidate, prev)
        if shared_rare:
            return True

        overlap = _significant_words(candidate) & _significant_words(prev)
        if len(overlap) >= 2:
            return True

        if _word_overlap_ratio(candidate, prev) >= 0.45:
            return True

    return False


def _shared_rare_words(a: str, b: str) -> set[str]:
    """Общие редкие subject-слова между двумя формулировками."""
    words_a = _significant_words(a)
    words_b = _significant_words(b)
    rare_a = {w for w in words_a if w in _RARE_SUBJECT_WORDS}
    rare_b = {w for w in words_b if w in _RARE_SUBJECT_WORDS}
    return rare_a & rare_b


def merge_topic_lists(*sources: list[str], limit: int = 40) -> list[str]:
    """Объединяет списки тем, убирая точные дубликаты.

    Args:
        *sources: списки от новых к старым.
        limit: максимум записей в результате.

    Returns:
        list[str]: объединённый список.
    """
    seen: set[str] = set()
    merged: list[str] = []
    for source in sources:
        for item in source:
            cleaned = item.strip()
            if not cleaned:
                continue
            key = _normalize(cleaned)
            if key in seen:
                continue
            seen.add(key)
            merged.append(cleaned)
            if len(merged) >= limit:
                return merged
    return merged


def _normalize(text: str) -> str:
    """Нормализует текст для сравнения.

    Args:
        text: исходная строка.

    Returns:
        str: нижний регистр без лишней пунктуации.
    """
    lowered = text.lower().replace("ё", "е")
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()


def _significant_words(text: str) -> set[str]:
    """Возвращает значимые слова длиной от 4 символов.

    Args:
        text: исходный текст.

    Returns:
        set[str]: слова без стоп-слов.
    """
    words = _normalize(text).split()
    return {w for w in words if len(w) >= 4 and w not in _STOP_WORDS}


def _word_overlap_ratio(a: str, b: str) -> float:
    """Доля пересечения значимых слов двух тем.

    Args:
        a: первая тема.
        b: вторая тема.

    Returns:
        float: коэффициент от 0 до 1.
    """
    words_a = _significant_words(a)
    words_b = _significant_words(b)
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    smaller = min(len(words_a), len(words_b))
    return len(intersection) / smaller
