"""Выгрузка статистики постов канала в CSV."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.infrastructure.models.post_metric import PostMetric
from app.utils.text_format import strip_html_tags

POST_STATS_EXPORT_DAYS = frozenset({14, 30})
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
CSV_HEADERS = ("Дата и время", "Текст поста", "Просмотры", "Охват", "Просмотры 24ч", "Просмотры 48ч", "Просмотры 72ч", "Подписчики на публикацию", "Клики кнопок", "Охват 24ч %")
DAILY_HEADERS = (
    "Дата",
    "Подписчики",
    "Прирост",
    "Подписки",
    "Отписки",
    "Новые просмотры",
    "Ср. охват постов",
)
_EXCEL_CELL_MAX = 32_000
_UNSAFE_CSV_PREFIXES = frozenset({"=", "+", "-", "@", "\t", "\r"})


@dataclass(frozen=True)
class PostStatsExportRow:
    """Одна строка выгрузки: дата, текст, просмотры, охват, age-buckets."""

    published_at: datetime | None
    text: str
    views: int | None
    reach: int | None = None
    views_24h: int | None = None
    views_48h: int | None = None
    views_72h: int | None = None
    subscribers_at_publication: int | None = None
    button_clicks: int | None = None


@dataclass(frozen=True)
class DailyDynamicsRow:
    """Дневная динамика канала."""

    day: date
    subscribers: int | None
    growth: int | None
    subscriptions: int | None
    unsubscribes: int | None
    new_views: int | None
    avg_reach: float | None


@dataclass(frozen=True)
class ChannelExportSummary:
    """Сводка канала за период выгрузки."""

    channel_name: str
    days: int
    period_start: datetime
    period_end: datetime
    subscribers_start: int | None
    subscribers_end: int | None
    subscribers_growth: int | None
    subscriptions: int | None
    unsubscribes: int | None
    new_views: int | None
    avg_views: float | None
    avg_reach: float | None
    subscriptions_estimated: bool


def _fmt_reach_pct(row: PostStatsExportRow) -> str:
    """Охват за 24ч = views_24h / subscribers_at_publication * 100."""
    if not row.views_24h or not row.subscribers_at_publication:
        return ""
    if row.subscribers_at_publication <= 0:
        return ""
    return f"{(row.views_24h / row.subscribers_at_publication) * 100:.1f}"


def format_export_datetime(value: datetime | None) -> str:
    """Форматирует момент публикации как МСК ``дд.мм.гггг чч:мм``.

    Args:
        value: момент времени (UTC или naive=UTC).

    Returns:
        str: дата и время или пустая строка.
    """
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M")


def _csv_safe(value: str) -> str:
    """Нейтрализует CSV-инъекцию формул Excel."""
    if value and value[0] in _UNSAFE_CSV_PREFIXES:
        return f"'{value}"
    return value


def _plain(value: str | None) -> str:
    """HTML → plain text без тегов."""
    if not value:
        return ""
    return strip_html_tags(value)


def _processed_post_export_text(post: object) -> str:
    """Полный текст поста: для статьи — анонс + тело, иначе rewritten_text."""
    teaser = _plain(getattr(post, "rewritten_text", None))
    body = _plain(getattr(post, "article_body", None))
    title = (getattr(post, "article_title", None) or "").strip()
    parts: list[str] = []
    if teaser:
        parts.append(teaser)
    elif title:
        parts.append(title)
    if body:
        parts.append(body)
    return "\n\n".join(parts)


def _as_utc(value: datetime) -> datetime:
    """Приводит datetime к UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def format_export_date(value: date | datetime | None) -> str:
    """Форматирует дату как МСК ``дд.мм.гггг``."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return _as_utc(value).astimezone(MOSCOW_TZ).strftime("%d.%m.%Y")
    return value.strftime("%d.%m.%Y")


def msk_day(value: datetime) -> date:
    """Календарный день в МСК."""
    return _as_utc(value).astimezone(MOSCOW_TZ).date()


def _fmt_int(value: int | None, *, signed: bool = False) -> str:
    """Целое для ячейки CSV."""
    if value is None:
        return ""
    if signed and value > 0:
        return f"+{value}"
    return str(value)


def _fmt_float(value: float | None) -> str:
    """Число с одним знаком после запятой."""
    if value is None:
        return ""
    return str(value)


def _mean(values: list[int]) -> float | None:
    """Среднее с одним знаком, либо None."""
    if not values:
        return None
    return round(sum(values) / len(values), 1)


def export_row_from_metric(metric: PostMetric) -> PostStatsExportRow:
    """Собирает строку выгрузки из метрики поста.

    Args:
        metric: метрики поста, опционально с processed_post.

    Returns:
        PostStatsExportRow: дата, текст, просмотры, охват.
    """
    published_at = metric.published_at or metric.collected_at
    post = getattr(metric, "processed_post", None)
    text = _processed_post_export_text(post) if post is not None else ""
    if not text:
        text = (getattr(metric, "post_text", None) or "").strip()
    if len(text) > _EXCEL_CELL_MAX:
        text = f"{text[: _EXCEL_CELL_MAX - 1]}…"
    return PostStatsExportRow(
        published_at=published_at,
        text=text,
        views=metric.views,
        reach=getattr(metric, "reach", None),
        views_24h=getattr(metric, "views_24h", None),
        views_48h=getattr(metric, "views_48h", None),
        views_72h=getattr(metric, "views_72h", None),
        subscribers_at_publication=getattr(
            metric, "subscribers_at_publication", None
        ),
        button_clicks=getattr(metric, "button_clicks", None),
    )


def compute_export_dynamics(
    snapshots: list[object],
    *,
    channel_name: str,
    days: int,
    since: datetime,
    until: datetime,
    posts: list[PostStatsExportRow],
    joins_by_day: dict[date, int] | None = None,
    leaves_by_day: dict[date, int] | None = None,
    subscriptions_total: int | None = None,
    unsubscribes_total: int | None = None,
) -> tuple[ChannelExportSummary, list[DailyDynamicsRow]]:
    """Сводка и дневная динамика по снимкам и постам.

    Подписки/отписки MAX передаются готовыми; для остальных платформ
    отписки — сумма падений счётчика, подписки = прирост + отписки.

    Args:
        snapshots: снимки от старых к новым (можно с baseline до ``since``).
        channel_name: имя канала.
        days: 14 или 30.
        since: начало периода UTC.
        until: конец периода UTC.
        posts: посты периода.
        joins_by_day: фактические вступления по дням (MAX).
        leaves_by_day: фактические отписки по дням (MAX).
        subscriptions_total: фактические подписки за период.
        unsubscribes_total: фактические отписки за период.

    Returns:
        tuple: сводка и строки по дням.
    """
    since = _as_utc(since)
    until = _as_utc(until)
    ordered = sorted(
        snapshots,
        key=lambda item: _as_utc(item.captured_at),
    )

    unsubs_by_day: dict[date, int] = {}
    views_by_day: dict[date, int] = {}
    last_sub_by_day: dict[date, int] = {}
    last_sub_before: int | None = None

    for index, snapshot in enumerate(ordered):
        captured = _as_utc(snapshot.captured_at)
        day = msk_day(captured)
        subscribers = snapshot.subscribers
        if subscribers is not None:
            last_sub_by_day[day] = subscribers
            if captured < since:
                last_sub_before = subscribers
        if index == 0:
            continue
        previous = ordered[index - 1]
        prev_sub = previous.subscribers
        curr_sub = snapshot.subscribers
        if prev_sub is not None and curr_sub is not None and curr_sub < prev_sub:
            drop = prev_sub - curr_sub
            unsubs_by_day[day] = unsubs_by_day.get(day, 0) + drop
        prev_views = previous.total_views
        curr_views = snapshot.total_views
        if prev_views is not None and curr_views is not None and curr_views > prev_views:
            views_by_day[day] = views_by_day.get(day, 0) + (curr_views - prev_views)

    posts_by_day: dict[date, list[PostStatsExportRow]] = {}
    for post in posts:
        if post.published_at is None:
            continue
        posts_by_day.setdefault(msk_day(post.published_at), []).append(post)

    start_day = msk_day(since)
    end_day = msk_day(until)
    daily: list[DailyDynamicsRow] = []
    carried_sub = last_sub_before
    cursor = start_day
    while cursor <= end_day:
        if cursor in last_sub_by_day:
            carried_sub = last_sub_by_day[cursor]
        day_unsubs = unsubs_by_day.get(cursor, 0)
        if leaves_by_day is not None:
            day_unsubs = leaves_by_day.get(cursor, 0)
        prev_sub = daily[-1].subscribers if daily else last_sub_before
        growth = None
        if carried_sub is not None and prev_sub is not None:
            growth = carried_sub - prev_sub
        elif carried_sub is not None and prev_sub is None:
            growth = 0
        if joins_by_day is not None:
            day_joins = joins_by_day.get(cursor, 0)
        elif growth is None:
            day_joins = None
        else:
            day_joins = max(0, growth + day_unsubs)
        day_posts = posts_by_day.get(cursor, [])
        reach_values = [
            p.reach if p.reach is not None else p.views
            for p in day_posts
            if (p.reach if p.reach is not None else p.views) is not None
        ]
        daily.append(
            DailyDynamicsRow(
                day=cursor,
                subscribers=carried_sub,
                growth=growth,
                subscriptions=day_joins,
                unsubscribes=day_unsubs if ordered else None,
                new_views=views_by_day.get(cursor),
                avg_reach=_mean([v for v in reach_values if v is not None]),
            )
        )
        cursor += timedelta(days=1)

    window_unsubs = 0
    has_unsubs = False
    for snap_day, amount in unsubs_by_day.items():
        if start_day <= snap_day <= end_day:
            window_unsubs += amount
            has_unsubs = True

    subscribers_end = carried_sub
    subscribers_start = last_sub_before
    if subscribers_start is None and daily:
        subscribers_start = next(
            (row.subscribers for row in daily if row.subscribers is not None),
            None,
        )
    growth_total = None
    if subscribers_start is not None and subscribers_end is not None:
        growth_total = subscribers_end - subscribers_start

    estimated_unsubs = window_unsubs if has_unsubs else None
    unsubscribes = (
        unsubscribes_total if unsubscribes_total is not None else estimated_unsubs
    )
    if subscriptions_total is not None:
        subscriptions = subscriptions_total
        estimated = False
    elif growth_total is not None and unsubscribes is not None:
        subscriptions = max(0, growth_total + unsubscribes)
        estimated = True
    else:
        subscriptions = None
        estimated = True

    new_views = sum(v for v in views_by_day.values() if v) or None
    if new_views == 0:
        new_views = 0 if views_by_day else None

    view_values = [p.views for p in posts if p.views is not None]
    reach_values = [
        p.reach if p.reach is not None else p.views
        for p in posts
        if (p.reach if p.reach is not None else p.views) is not None
    ]

    summary = ChannelExportSummary(
        channel_name=channel_name,
        days=days,
        period_start=since,
        period_end=until,
        subscribers_start=subscribers_start,
        subscribers_end=subscribers_end,
        subscribers_growth=growth_total,
        subscriptions=subscriptions,
        unsubscribes=unsubscribes,
        new_views=new_views,
        avg_views=_mean(view_values),
        avg_reach=_mean([v for v in reach_values if v is not None]),
        subscriptions_estimated=estimated,
    )
    return summary, daily


def build_channel_stats_csv(
    summary: ChannelExportSummary,
    daily: list[DailyDynamicsRow],
    posts: list[PostStatsExportRow],
) -> bytes:
    """Полный отчёт: сводка, динамика по дням, посты.

    Args:
        summary: сводка периода.
        daily: дневные строки.
        posts: посты периода.

    Returns:
        bytes: CSV UTF-8 BOM.
    """
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=";",
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    subs_label = (
        "Подписки (оценка по приросту и отпискам)"
        if summary.subscriptions_estimated
        else "Подписки"
    )
    unsubs_label = (
        "Отписки (оценка по падению счётчика)"
        if summary.subscriptions_estimated
        else "Отписки"
    )
    writer.writerow([f"Сводка за {summary.days} дней"])
    writer.writerow(["Канал", _csv_safe(summary.channel_name)])
    writer.writerow(
        [
            "Период",
            f"{format_export_date(summary.period_start)} — {format_export_date(summary.period_end)}",
        ]
    )
    writer.writerow([])
    writer.writerow(["Показатель", "Значение"])
    writer.writerow(["Подписчики на начало", _fmt_int(summary.subscribers_start)])
    writer.writerow(["Подписчики на конец", _fmt_int(summary.subscribers_end)])
    writer.writerow(
        ["Прирост подписчиков", _fmt_int(summary.subscribers_growth, signed=True)]
    )
    writer.writerow([subs_label, _fmt_int(summary.subscriptions)])
    writer.writerow([unsubs_label, _fmt_int(summary.unsubscribes)])
    writer.writerow(["Новые просмотры", _fmt_int(summary.new_views)])
    writer.writerow(["Средние просмотры на пост", _fmt_float(summary.avg_views)])
    writer.writerow(["Средний охват на пост", _fmt_float(summary.avg_reach)])
    writer.writerow([])
    writer.writerow(["Динамика по дням"])
    writer.writerow(DAILY_HEADERS)
    for row in daily:
        writer.writerow(
            [
                format_export_date(row.day),
                _fmt_int(row.subscribers),
                _fmt_int(row.growth, signed=True),
                _fmt_int(row.subscriptions),
                _fmt_int(row.unsubscribes),
                _fmt_int(row.new_views),
                _fmt_float(row.avg_reach),
            ]
        )
    writer.writerow([])
    writer.writerow(["Посты"])
    writer.writerow(CSV_HEADERS)
    for row in posts:
        writer.writerow(
            [
                format_export_datetime(row.published_at),
                _csv_safe(row.text),
                _fmt_int(row.views),
                _fmt_int(row.reach),
                _fmt_int(row.views_24h),
                _fmt_int(row.views_48h),
                _fmt_int(row.views_72h),
                _fmt_int(row.subscribers_at_publication),
                _fmt_int(row.button_clicks),
                _fmt_reach_pct(row),
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def build_posts_stats_csv(rows: list[PostStatsExportRow]) -> bytes:
    """CSV с постами (UTF-8 BOM, разделитель ;)."""
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=";",
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writerow(CSV_HEADERS)
    for row in rows:
        writer.writerow(
            [
                format_export_datetime(row.published_at),
                _csv_safe(row.text),
                _fmt_int(row.views),
                _fmt_int(row.reach),
                _fmt_int(row.views_24h),
                _fmt_int(row.views_48h),
                _fmt_int(row.views_72h),
                _fmt_int(row.subscribers_at_publication),
                _fmt_int(row.button_clicks),
                _fmt_reach_pct(row),
            ]
        )
    return buffer.getvalue().encode("utf-8-sig")


def posts_stats_export_filename(channel_name: str, days: int) -> str:
    """Имя файла выгрузки.

    Args:
        channel_name: название канала.
        days: период в днях.

    Returns:
        str: ``{канал}_{days}d.csv``.
    """
    slug = re.sub(r"[^\w]+", "_", channel_name.strip(), flags=re.UNICODE)
    slug = re.sub(r"_+", "_", slug).strip("_") or "channel"
    return f"{slug}_{days}d.csv"
