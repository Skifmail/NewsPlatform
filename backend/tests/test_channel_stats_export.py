"""Тесты выгрузки статистики постов канала в CSV."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.models.channel import Channel
from app.services.channel_stats_export import (
    POST_STATS_EXPORT_DAYS,
    PostStatsExportRow,
    build_channel_stats_csv,
    build_posts_stats_csv,
    compute_export_dynamics,
    export_row_from_metric,
    format_export_datetime,
    posts_stats_export_filename,
)


@pytest.fixture
def channel() -> Channel:
    """Тестовый канал для выгрузки."""
    return Channel(
        id=1,
        name="Test TG",
        platform="telegram",
        platform_id="@test",
        topic="it",
        is_active=True,
    )


def test_format_export_datetime_moscow() -> None:
    """UTC-момент форматируется как МСК dd.mm.yyyy hh:mm."""
    value = datetime(2026, 8, 21, 13, 5, tzinfo=UTC)
    assert format_export_datetime(value) == "21.08.2026 16:05"


def test_format_export_datetime_naive_treated_as_utc() -> None:
    """Naive datetime считается UTC."""
    value = datetime(2026, 8, 21, 13, 5)
    assert format_export_datetime(value) == "21.08.2026 16:05"


def test_format_export_datetime_empty() -> None:
    """Пустая дата -> пустая строка."""
    assert format_export_datetime(None) == ""


def test_build_csv_headers_and_bom() -> None:
    """CSV с BOM, разделителем ; и русскими заголовками."""
    payload = build_posts_stats_csv(
        [
            PostStatsExportRow(
                published_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
                text="Первый пост",
                views=1200,
            )
        ]
    )
    assert payload.startswith(b"\xef\xbb\xbf")
    text = payload.decode("utf-8-sig")
    assert text.startswith("Дата и время;Текст поста;Просмотры")
    assert "10.08.2026 11:00" in text
    assert "Первый пост" in text
    assert "1200" in text


def test_build_csv_quotes_semicolon_in_text() -> None:
    """Текст с ; экранируется кавычками."""
    payload = build_posts_stats_csv(
        [
            PostStatsExportRow(
                published_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
                text="Заголовок; продолжение",
                views=None,
            )
        ]
    )
    text = payload.decode("utf-8-sig")
    assert '"Заголовок; продолжение"' in text


def test_csv_formula_injection_prefix() -> None:
    """Формулы Excel экранируются апострофом."""
    payload = build_posts_stats_csv(
        [
            PostStatsExportRow(
                published_at=None,
                text="=CMD()",
                views=1,
            )
        ]
    )
    assert "'=CMD()" in payload.decode("utf-8-sig")


def test_export_row_prefers_rewritten_text_and_strips_html() -> None:
    """Для новости берётся rewritten_text без HTML."""
    metric = SimpleNamespace(
        published_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        collected_at=datetime(2026, 8, 11, 8, 0, tzinfo=UTC),
        views=10,
        post_text="с платформы",
        processed_post=SimpleNamespace(rewritten_text="<b>Наш</b> пост"),
    )
    row = export_row_from_metric(metric)
    assert row.text == "Наш пост"
    assert row.published_at == metric.published_at
    assert row.views == 10


def test_export_row_includes_full_article_body() -> None:
    """Для статьи в CSV анонс и полный текст, не только карточка."""
    metric = SimpleNamespace(
        published_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        collected_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        views=42,
        post_text="короткий анонс с платформы",
        processed_post=SimpleNamespace(
            rewritten_text="<b>Крючок</b> анонса",
            article_title="Заголовок",
            article_body="<p>Первый абзац статьи.</p><p>Второй абзац.</p>",
        ),
    )
    row = export_row_from_metric(metric)
    assert "Крючок анонса" in row.text
    assert "Первый абзац статьи." in row.text
    assert "Второй абзац." in row.text
    assert row.text != "короткий анонс с платформы"


def test_export_row_falls_back_to_platform_text() -> None:
    """Без processed_post используется текст с платформы."""
    metric = SimpleNamespace(
        published_at=None,
        collected_at=datetime(2026, 8, 11, 8, 0, tzinfo=UTC),
        views=3,
        post_text="  текст из Telegram  ",
        processed_post=None,
    )
    row = export_row_from_metric(metric)
    assert row.text == "текст из Telegram"
    assert row.published_at == metric.collected_at


def test_export_filename_slugifies_channel_name() -> None:
    """Имя файла содержит канал и период."""
    assert posts_stats_export_filename("IT Новости!", 14) == "IT_Новости_14d.csv"
    assert posts_stats_export_filename("   ", 30) == "channel_30d.csv"


def test_export_days_allowed() -> None:
    """Допустимы только 14 и 30 дней."""
    assert POST_STATS_EXPORT_DAYS == frozenset({14, 30})


@pytest.mark.asyncio
async def test_service_rejects_invalid_days() -> None:
    """Неверный период вызывает ValueError."""
    from app.services.channel_analytics_service import ChannelAnalyticsService

    service = ChannelAnalyticsService(MagicMock())
    with pytest.raises(ValueError, match="14 или 30"):
        await service.export_channel_post_stats(1, days=7)


@pytest.mark.asyncio
async def test_service_export_builds_csv(channel) -> None:
    """Сервис отдаёт имя файла и CSV по метрикам канала."""
    from app.services.channel_analytics_service import ChannelAnalyticsService

    metric = SimpleNamespace(
        published_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        collected_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        views=500,
        post_text=None,
        processed_post=SimpleNamespace(rewritten_text="Текст поста"),
    )
    service = ChannelAnalyticsService(MagicMock())
    service._channels.get_by_id = AsyncMock(return_value=channel)
    service._post_metrics.list_for_channel_since = AsyncMock(return_value=[metric])
    service._snapshots.latest_before = AsyncMock(return_value=None)
    service._snapshots.list_for_channel = AsyncMock(return_value=[])

    filename, payload = await service.export_channel_post_stats(1, days=14)

    assert filename == "Test_TG_14d.csv"
    text = payload.decode("utf-8-sig")
    assert "Текст поста" in text
    assert "500" in text
    assert "Прирост подписчиков" in text
    assert "Динамика по дням" in text
    assert "Подписки" in text
    assert "Отписки" in text
    _, kwargs = service._post_metrics.list_for_channel_since.await_args
    since = kwargs["since"]
    expected = datetime.now(UTC) - timedelta(days=14)
    assert abs((expected - since).total_seconds()) < 5


@pytest.mark.asyncio
async def test_service_export_30_days_window(channel) -> None:
    """Период 30 дней передаёт since ≈ now-30d."""
    from app.services.channel_analytics_service import ChannelAnalyticsService

    service = ChannelAnalyticsService(MagicMock())
    service._channels.get_by_id = AsyncMock(return_value=channel)
    service._post_metrics.list_for_channel_since = AsyncMock(return_value=[])
    service._snapshots.latest_before = AsyncMock(return_value=None)
    service._snapshots.list_for_channel = AsyncMock(return_value=[])

    await service.export_channel_post_stats(1, days=30)

    _, kwargs = service._post_metrics.list_for_channel_since.await_args
    since = kwargs["since"]
    expected = datetime.now(UTC) - timedelta(days=30)
    assert abs((expected - since).total_seconds()) < 5


def test_export_row_views_zero() -> None:
    """Ноль просмотров отличается от отсутствия значения."""
    metric = SimpleNamespace(
        published_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        collected_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
        views=0,
        post_text="пост",
        processed_post=None,
    )
    row = export_row_from_metric(metric)
    payload = build_posts_stats_csv([row]).decode("utf-8-sig")
    assert payload.rstrip().endswith(";0;")


def test_compute_export_dynamics_growth_unsubs_and_views() -> None:
    """Прирост, отписки и новые просмотры считаются по снимкам."""
    snapshots = [
        SimpleNamespace(
            captured_at=datetime(2026, 8, 6, 12, 0, tzinfo=UTC),
            subscribers=100,
            total_views=1000,
        ),
        SimpleNamespace(
            captured_at=datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
            subscribers=110,
            total_views=1300,
        ),
        SimpleNamespace(
            captured_at=datetime(2026, 8, 9, 12, 0, tzinfo=UTC),
            subscribers=107,
            total_views=1400,
        ),
    ]
    posts = [
        PostStatsExportRow(
            published_at=datetime(2026, 8, 8, 10, 0, tzinfo=UTC),
            text="пост",
            views=200,
            reach=180,
        )
    ]
    summary, daily = compute_export_dynamics(
        snapshots,
        channel_name="Test",
        days=14,
        since=datetime(2026, 8, 7, 12, 0, tzinfo=UTC),
        until=datetime(2026, 8, 10, 12, 0, tzinfo=UTC),
        posts=posts,
    )
    assert summary.subscribers_start == 100
    assert summary.subscribers_end == 107
    assert summary.subscribers_growth == 7
    assert summary.unsubscribes == 3
    assert summary.subscriptions == 10
    assert summary.subscriptions_estimated is True
    assert summary.new_views == 400
    assert summary.avg_reach == 180.0
    by_day = {row.day.isoformat(): row for row in daily}
    assert by_day["2026-08-08"].growth == 10
    assert by_day["2026-08-09"].unsubscribes == 3
    assert by_day["2026-08-09"].growth == -3


def test_build_channel_stats_csv_has_sections() -> None:
    """Полный отчёт содержит сводку, дни и посты."""
    posts = [
        PostStatsExportRow(
            published_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
            text="Текст",
            views=10,
            reach=8,
        )
    ]
    summary, daily = compute_export_dynamics(
        [
            SimpleNamespace(
                captured_at=datetime(2026, 8, 10, 8, 0, tzinfo=UTC),
                subscribers=50,
                total_views=200,
            )
        ],
        channel_name="Канал",
        days=14,
        since=datetime(2026, 8, 10, 0, 0, tzinfo=UTC),
        until=datetime(2026, 8, 10, 23, 0, tzinfo=UTC),
        posts=posts,
    )
    text = build_channel_stats_csv(summary, daily, posts).decode("utf-8-sig")
    assert "Сводка за 14 дней" in text
    assert "Динамика по дням" in text
    assert "Посты" in text
    assert "Охват" in text
