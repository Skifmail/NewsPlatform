"""Тесты оценки здоровья конвейера публикаций."""

from datetime import UTC, datetime, timedelta

from app.domain.pipeline_health import (
    CRITICAL,
    OK,
    WARNING,
    assess_pipeline,
)

NOW = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)


def test_ok_when_recently_published() -> None:
    # Arrange
    verdict = assess_pipeline(
        now=NOW,
        last_publish_at=NOW - timedelta(minutes=20),
        last_fetch_at=NOW - timedelta(minutes=5),
        failed_jobs_24h=0,
        in_active_window=True,
    )
    # Assert
    assert verdict.status == OK


def test_critical_silent_failure_parsing_but_no_publish() -> None:
    """Ключевой кейс: парсинг свежий, а публикаций давно нет → critical."""
    verdict = assess_pipeline(
        now=NOW,
        last_publish_at=NOW - timedelta(hours=8),
        last_fetch_at=NOW - timedelta(minutes=10),
        failed_jobs_24h=40,
        in_active_window=True,
    )
    assert verdict.status == CRITICAL
    assert "парсятся" in verdict.reason


def test_warning_when_publish_gap_moderate() -> None:
    verdict = assess_pipeline(
        now=NOW,
        last_publish_at=NOW - timedelta(hours=4),
        last_fetch_at=NOW - timedelta(minutes=10),
        failed_jobs_24h=0,
        in_active_window=True,
    )
    assert verdict.status == WARNING


def test_ok_outside_active_window_even_if_stale() -> None:
    """Ночью долгий перерыв — это норма, не тревога."""
    verdict = assess_pipeline(
        now=NOW,
        last_publish_at=NOW - timedelta(hours=8),
        last_fetch_at=NOW - timedelta(hours=8),
        failed_jobs_24h=0,
        in_active_window=False,
    )
    assert verdict.status == OK


def test_critical_when_never_published() -> None:
    verdict = assess_pipeline(
        now=NOW,
        last_publish_at=None,
        last_fetch_at=NOW,
        failed_jobs_24h=0,
        in_active_window=True,
    )
    assert verdict.status == CRITICAL


def test_warning_on_many_failed_jobs_even_if_publishing() -> None:
    verdict = assess_pipeline(
        now=NOW,
        last_publish_at=NOW - timedelta(minutes=15),
        last_fetch_at=NOW - timedelta(minutes=5),
        failed_jobs_24h=25,
        in_active_window=True,
    )
    assert verdict.status == WARNING
