"""Кодирование текущего этапа фоновой задачи для UI."""

STAGE_SEPARATOR = "|"


def encode_stage(progress: int, detail: str) -> str:
    """Формирует значение result_summary для running-задачи.

    Args:
        progress: процент 0–100 для прогресс-бара.
        detail: человекочитаемый текст этапа.

    Returns:
        str: строка вида ``42|Поиск материалов…``.
    """
    return f"{progress}{STAGE_SEPARATOR}{detail}"


def decode_stage(raw: str | None) -> tuple[int | None, str | None]:
    """Разбирает result_summary running-задачи.

    Args:
        raw: значение из БД.

    Returns:
        tuple[int | None, str | None]: прогресс и текст этапа.
    """
    if not raw:
        return None, None
    if STAGE_SEPARATOR not in raw:
        return None, raw
    head, _, tail = raw.partition(STAGE_SEPARATOR)
    if head.isdigit() and tail:
        return int(head), tail
    return None, raw
