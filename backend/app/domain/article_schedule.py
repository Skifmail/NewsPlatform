"""Расписание выхода статей по конкретным временам (МСК).

Альтернатива режиму «окно + интервал»: канал задаёт список точных времён
публикации по московскому времени (например 09:00 и 18:00). МСК — фиксированный
UTC+3 (в России нет перехода на летнее время).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, time, timedelta, timezone

MSK = timezone(timedelta(hours=3))
_DEFAULT_CATCHUP_MINUTES = 90
_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def parse_publish_times(raw: str | None) -> list[time]:
    """Парсит строку времён «HH:MM,HH:MM» (МСК) в отсортированный список.

    Args:
        raw: строка вида "09:00, 18:00" или None.

    Returns:
        list[time]: уникальные валидные времена по возрастанию.
    """
    if not raw:
        return []
    result: dict[tuple[int, int], time] = {}
    for chunk in raw.replace(";", ",").split(","):
        piece = chunk.strip()
        match = _TIME_RE.match(piece)
        if not match:
            continue
        hh, mm = int(match.group(1)), int(match.group(2))
        result[(hh, mm)] = time(hour=hh, minute=mm)
    return [result[key] for key in sorted(result)]


def format_publish_times(times: list[time]) -> str:
    """Сериализует список времён обратно в строку «HH:MM,HH:MM»."""
    return ",".join(f"{t.hour:02d}:{t.minute:02d}" for t in times)


def due_slot(
    now_utc: datetime,
    raw_times: str | None,
    last_run_utc: datetime | None,
    *,
    catchup_minutes: int = _DEFAULT_CATCHUP_MINUTES,
) -> datetime | None:
    """Возвращает наступивший слот публикации (в UTC) или None.

    Слот «свежий», если текущий момент попал в окно
    [slot, slot + catchup_minutes) и с прошлого запуска этот слот ещё не
    отрабатывал (last_run < slot). Проверяются слоты сегодня и вчера по МСК
    (вчерашние поздние времена возле полуночи).

    Args:
        now_utc: текущий момент (UTC, aware).
        raw_times: строка времён по МСК.
        last_run_utc: момент последней генерации (UTC) или None.
        catchup_minutes: сколько минут слот считается актуальным.

    Returns:
        datetime | None: слот в UTC (наиболее поздний из подходящих) или None.
    """
    times = parse_publish_times(raw_times)
    if not times:
        return None
    if now_utc.tzinfo is None:
        now_utc = now_utc.replace(tzinfo=UTC)
    if last_run_utc is not None and last_run_utc.tzinfo is None:
        last_run_utc = last_run_utc.replace(tzinfo=UTC)

    now_msk = now_utc.astimezone(MSK)
    window = timedelta(minutes=max(1, catchup_minutes))

    candidates: list[datetime] = []
    for day_offset in (0, -1):
        day = (now_msk + timedelta(days=day_offset)).date()
        for t in times:
            slot_msk = datetime.combine(day, t, tzinfo=MSK)
            slot_utc = slot_msk.astimezone(UTC)
            if slot_utc <= now_utc < slot_utc + window and (
                last_run_utc is None or last_run_utc < slot_utc
            ):
                candidates.append(slot_utc)

    return max(candidates) if candidates else None
