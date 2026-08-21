"""Выгрузка статистики постов канала в CSV."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.infrastructure.models.post_metric import PostMetric
from app.utils.text_format import strip_html_tags

POST_STATS_EXPORT_DAYS = frozenset({14, 30})
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
CSV_HEADERS = ("Дата и время", "Текст поста", "Просмотры")
_EXCEL_CELL_MAX = 32_000
_UNSAFE_CSV_PREFIXES = frozenset({"=", "+", "-", "@", "\t", "\r"})


@dataclass(frozen=True)
class PostStatsExportRow:
    """Одна строка выгрузки: дата, текст, просмотры."""

    published_at: datetime | None
    text: str
    views: int | None


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


def export_row_from_metric(metric: PostMetric) -> PostStatsExportRow:
    """Собирает строку выгрузки из метрики поста.

    Args:
        metric: метрики поста, опционально с processed_post.

    Returns:
        PostStatsExportRow: дата, текст, просмотры.
    """
    published_at = metric.published_at or metric.collected_at
    text = ""
    post = getattr(metric, "processed_post", None)
    rewritten = getattr(post, "rewritten_text", None) if post is not None else None
    if rewritten:
        text = strip_html_tags(rewritten)
    if not text:
        text = (getattr(metric, "post_text", None) or "").strip()
    if len(text) > _EXCEL_CELL_MAX:
        text = f"{text[: _EXCEL_CELL_MAX - 1]}…"
    return PostStatsExportRow(
        published_at=published_at,
        text=text,
        views=metric.views,
    )


def build_posts_stats_csv(rows: list[PostStatsExportRow]) -> bytes:
    """Строит CSV (UTF-8 BOM, разделитель ;) для Excel.

    Args:
        rows: строки выгрузки.

    Returns:
        bytes: содержимое файла.
    """
    buffer = io.StringIO()
    writer = csv.writer(
        buffer,
        delimiter=";",
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writerow(CSV_HEADERS)
    for row in rows:
        views = "" if row.views is None else str(row.views)
        writer.writerow(
            [
                format_export_datetime(row.published_at),
                _csv_safe(row.text),
                views,
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
