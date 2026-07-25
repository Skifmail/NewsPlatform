"""Оценка здоровья конвейера публикаций (чистая логика, без БД).

Главная цель — ловить «тихий» сбой: статистика собирается и материалы
парсятся, но ничего не публикуется. В этом случае панель должна кричать,
а не показывать зелёный статус.
"""

from dataclasses import dataclass
from datetime import datetime

# Порог «давно не публиковали» в активном окне (МСК 07:00–23:00).
STALL_WARNING_HOURS = 3
STALL_CRITICAL_HOURS = 6
# Порог «многовато упавших задач за сутки».
FAILED_JOBS_WARN = 10
# Свежесть парсинга, при которой считаем, что материалы поступают.
FETCH_FRESH_HOURS = 2

OK = "ok"
WARNING = "warning"
CRITICAL = "critical"


@dataclass(frozen=True)
class HealthVerdict:
    """Итог оценки: статус и человекочитаемая причина."""

    status: str
    reason: str


def _hours_between(now: datetime, past: datetime) -> float:
    """Часы между моментами (>=0)."""
    return max(0.0, (now - past).total_seconds() / 3600.0)


def assess_pipeline(
    *,
    now: datetime,
    last_publish_at: datetime | None,
    last_fetch_at: datetime | None,
    failed_jobs_24h: int,
    in_active_window: bool,
) -> HealthVerdict:
    """Оценивает состояние конвейера публикаций.

    Args:
        now: текущий момент (UTC, aware).
        last_publish_at: время последней публикации, либо None.
        last_fetch_at: время последнего успешного парсинга, либо None.
        failed_jobs_24h: число упавших фоновых задач за 24 часа.
        in_active_window: попадает ли `now` в активное окно публикаций (МСК).

    Returns:
        HealthVerdict: статус (ok/warning/critical) и причина.
    """
    if last_publish_at is None:
        return HealthVerdict(CRITICAL, "Публикаций ещё не было ни разу")

    hours_since = _hours_between(now, last_publish_at)
    fetch_ok = (
        last_fetch_at is not None
        and _hours_between(now, last_fetch_at) <= FETCH_FRESH_HOURS
    )
    h = round(hours_since)

    if not in_active_window:
        if failed_jobs_24h >= FAILED_JOBS_WARN:
            return HealthVerdict(
                WARNING, f"Ночной перерыв, но за сутки {failed_jobs_24h} упавших задач"
            )
        return HealthVerdict(OK, "Ночной перерыв — публикации возобновятся по расписанию")

    if hours_since >= STALL_CRITICAL_HOURS:
        if fetch_ok:
            return HealthVerdict(
                CRITICAL,
                f"Материалы парсятся, но {h} ч нет публикаций — вероятно, ошибка конвейера",
            )
        return HealthVerdict(CRITICAL, f"{h} ч нет публикаций")

    if hours_since >= STALL_WARNING_HOURS:
        return HealthVerdict(WARNING, f"{h} ч без публикаций — стоит проверить")

    if failed_jobs_24h >= FAILED_JOBS_WARN:
        return HealthVerdict(
            WARNING, f"Публикации идут, но за сутки {failed_jobs_24h} упавших задач"
        )

    return HealthVerdict(OK, "Публикации идут штатно")
