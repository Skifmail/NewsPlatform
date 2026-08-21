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


def export_row_from_metric(metric: PostMetric) -> PostStatsExportRow:
    """Собирает строку выгрузки из метрики поста.

    Args:
        metric: метрики поста, опционально с processed_post.

    Returns:
        PostStatsExportRow: дата, текст, просмотры.
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
