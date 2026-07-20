"""Тесты парсинга и защищённого сбора нативной статистики Telegram."""

from types import SimpleNamespace

import pytest

from app.infrastructure.models.channel import Channel
from app.infrastructure.stats.telegram_stats import (
    TelegramStatsCollector,
    parse_broadcast_stats,
)


def _abs(current, previous):
    return SimpleNamespace(current=current, previous=previous)


def test_parse_broadcast_stats_full() -> None:
    stats = SimpleNamespace(
        followers=_abs(1500, 1400),
        views_per_post=_abs(320.0, 280.0),
        shares_per_post=_abs(12.5, 10.0),
        reactions_per_post=_abs(45.0, 40.0),
        enabled_notifications=SimpleNamespace(part=600.0, total=1500.0),
        period=SimpleNamespace(min_date=1_781_000_000, max_date=1_784_000_000),
    )
    dto = parse_broadcast_stats(stats)
    assert dto.followers == 1500
    assert dto.followers_prev == 1400
    assert dto.views_per_post == 320.0
    assert dto.shares_per_post == 12.5
    assert dto.reactions_per_post == 45.0
    assert dto.enabled_notifications_pct == 40.0  # 600/1500*100
    assert dto.period_min is not None
    assert dto.period_max is not None


def test_parse_broadcast_stats_missing_fields() -> None:
    """Отсутствующие поля не роняют парсинг (getattr-защита)."""
    dto = parse_broadcast_stats(SimpleNamespace())
    assert dto.followers is None
    assert dto.views_per_post is None
    assert dto.enabled_notifications_pct is None
    assert dto.period_min is None


def test_percent_zero_total_is_none() -> None:
    stats = SimpleNamespace(
        enabled_notifications=SimpleNamespace(part=0, total=0),
    )
    assert parse_broadcast_stats(stats).enabled_notifications_pct is None


@pytest.mark.asyncio
async def test_fetch_broadcast_stats_skips_on_error() -> None:
    """Если API падает (канал мал/нет прав) — тихо возвращаем None."""

    class _Client:
        async def __call__(self, _request):
            raise RuntimeError("CHAT_ADMIN_REQUIRED / stats unavailable")

    channel = Channel(
        id=5, name="ПАРАГРАФ", platform="telegram", platform_id="@paragraf", topic="it"
    )
    result = await TelegramStatsCollector()._fetch_broadcast_stats(
        _Client(), object(), channel
    )
    assert result is None


@pytest.mark.asyncio
async def test_fetch_broadcast_stats_parses_on_success() -> None:
    """Успешный ответ парсится в DTO."""

    stats = SimpleNamespace(
        followers=_abs(800, 750),
        views_per_post=_abs(100.0, 90.0),
        shares_per_post=None,
        reactions_per_post=None,
        enabled_notifications=SimpleNamespace(part=400, total=800),
        period=SimpleNamespace(min_date=1_781_000_000, max_date=1_784_000_000),
    )

    class _Client:
        async def __call__(self, _request):
            return stats

    channel = Channel(
        id=5, name="ПАРАГРАФ", platform="telegram", platform_id="@paragraf", topic="it"
    )
    result = await TelegramStatsCollector()._fetch_broadcast_stats(
        _Client(), object(), channel
    )
    assert result is not None
    assert result.followers == 800
    assert result.enabled_notifications_pct == 50.0
    assert result.shares_per_post is None
