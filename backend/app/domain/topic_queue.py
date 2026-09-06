"""Очередь редакционных тем канала (план на 1–2 недели)."""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

TopicStatus = Literal["pending", "in_progress", "published", "skipped"]

_VALID_STATUSES = frozenset({"pending", "in_progress", "published", "skipped"})


@dataclass
class TopicQueueItem:
    """Элемент редакционной очереди тем.

    Attributes:
        id: стабильный идентификатор.
        title: формулировка темы.
        status: статус в очереди.
        published_at: ISO-время публикации (UTC).
        published_post_id: ID processed_post после генерации.
        entities: ключевые сущности для антиповтора.
        notes: опциональная пометка редактора.
    """

    id: str
    title: str
    status: TopicStatus = "pending"
    published_at: str | None = None
    published_post_id: int | None = None
    entities: list[str] = field(default_factory=list)
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Сериализует элемент в JSON-совместимый dict."""
        return asdict(self)


def parse_topic_queue(raw: str | None) -> list[TopicQueueItem]:
    """Парсит JSON-очередь тем из поля канала.

    Args:
        raw: JSON-массив или пустая строка.

    Returns:
        list[TopicQueueItem]: элементы от старых к новым (порядок очереди).
    """
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    items: list[TopicQueueItem] = []
    for entry in data:
        item = _item_from_raw(entry)
        if item is not None:
            items.append(item)
    return items


def serialize_topic_queue(items: list[TopicQueueItem]) -> str:
    """Сериализует очередь тем в JSON.

    Args:
        items: элементы очереди.

    Returns:
        str: JSON-массив.
    """
    return json.dumps([item.to_dict() for item in items], ensure_ascii=False)


def parse_topics_from_text(text: str) -> list[str]:
    """Разбирает многострочный ввод редактора в список тем.

    Поддерживает нумерацию («1. …», «- …») и пустые строки.

    Args:
        text: сырой текст из textarea.

    Returns:
        list[str]: очищенные формулировки тем.
    """
    topics: list[str] = []
    for line in text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        cleaned = re.sub(r"^[\d]+[.)]\s*", "", cleaned)
        cleaned = re.sub(r"^[-•*]\s*", "", cleaned)
        cleaned = cleaned.strip()
        if cleaned:
            topics.append(cleaned)
    return topics


def append_topics(
    existing: list[TopicQueueItem],
    titles: list[str],
) -> list[TopicQueueItem]:
    """Добавляет новые pending-темы в конец очереди без дублей.

    Args:
        existing: текущая очередь.
        titles: новые формулировки.

    Returns:
        list[TopicQueueItem]: обновлённая очередь.
    """
    known = {_normalize(item.title) for item in existing if item.status != "skipped"}
    result = list(existing)
    for title in titles:
        key = _normalize(title)
        if not key or key in known:
            continue
        known.add(key)
        result.append(
            TopicQueueItem(
                id=uuid.uuid4().hex[:12],
                title=title.strip(),
                status="pending",
            )
        )
    return result


def next_pending(items: list[TopicQueueItem]) -> TopicQueueItem | None:
    """Возвращает следующую тему со статусом pending.

    Args:
        items: очередь.

    Returns:
        TopicQueueItem | None: первая pending-тема.
    """
    for item in items:
        if item.status == "pending":
            return item
    return None


def mark_in_progress(
    items: list[TopicQueueItem],
    item_id: str,
) -> list[TopicQueueItem]:
    """Помечает тему как in_progress (остальные in_progress → pending).

    Args:
        items: очередь.
        item_id: ID темы.

    Returns:
        list[TopicQueueItem]: обновлённая очередь.
    """
    updated: list[TopicQueueItem] = []
    for item in items:
        if item.id == item_id:
            updated.append(
                TopicQueueItem(
                    id=item.id,
                    title=item.title,
                    status="in_progress",
                    published_at=item.published_at,
                    published_post_id=item.published_post_id,
                    entities=list(item.entities),
                    notes=item.notes,
                )
            )
        elif item.status == "in_progress":
            updated.append(
                TopicQueueItem(
                    id=item.id,
                    title=item.title,
                    status="pending",
                    published_at=item.published_at,
                    published_post_id=item.published_post_id,
                    entities=list(item.entities),
                    notes=item.notes,
                )
            )
        else:
            updated.append(item)
    return updated


def mark_published(
    items: list[TopicQueueItem],
    item_id: str,
    *,
    published_post_id: int,
    entities: list[str] | None = None,
) -> list[TopicQueueItem]:
    """Помечает тему опубликованной.

    Args:
        items: очередь.
        item_id: ID темы.
        published_post_id: ID созданного processed_post.
        entities: сущности для истории антиповтора.

    Returns:
        list[TopicQueueItem]: обновлённая очередь.
    """
    now = datetime.now(UTC).isoformat()
    updated: list[TopicQueueItem] = []
    for item in items:
        if item.id != item_id:
            updated.append(item)
            continue
        updated.append(
            TopicQueueItem(
                id=item.id,
                title=item.title,
                status="published",
                published_at=now,
                published_post_id=published_post_id,
                entities=list(entities or item.entities),
                notes=item.notes,
            )
        )
    return updated


def mark_skipped(items: list[TopicQueueItem], item_id: str) -> list[TopicQueueItem]:
    """Помечает тему как пропущенную.

    Args:
        items: очередь.
        item_id: ID темы.

    Returns:
        list[TopicQueueItem]: обновлённая очередь.
    """
    updated: list[TopicQueueItem] = []
    for item in items:
        if item.id != item_id:
            updated.append(item)
            continue
        updated.append(
            TopicQueueItem(
                id=item.id,
                title=item.title,
                status="skipped",
                published_at=item.published_at,
                published_post_id=item.published_post_id,
                entities=list(item.entities),
                notes=item.notes,
            )
        )
    return updated


def queue_summary(items: list[TopicQueueItem]) -> dict[str, int]:
    """Считает темы по статусам для UI.

    Args:
        items: очередь.

    Returns:
        dict[str, int]: счётчики pending/published/…
    """
    counts = {"pending": 0, "in_progress": 0, "published": 0, "skipped": 0, "total": 0}
    for item in items:
        counts["total"] += 1
        if item.status in counts:
            counts[item.status] += 1
    return counts


def pending_titles(items: list[TopicQueueItem]) -> list[str]:
    """Список формулировок pending-тем.

    Args:
        items: очередь.

    Returns:
        list[str]: заголовки.
    """
    return [item.title for item in items if item.status == "pending"]


def published_titles(items: list[TopicQueueItem]) -> list[str]:
    """Список опубликованных тем (для антиповтора).

    Args:
        items: очередь.

    Returns:
        list[str]: заголовки.
    """
    return [item.title for item in items if item.status == "published"]



def remove_topic(items: list[TopicQueueItem], item_id: str) -> list[TopicQueueItem]:
    """Удаляет тему из очереди полностью (включая опубликованные).

    Args:
        items: очередь.
        item_id: ID темы.

    Returns:
        list[TopicQueueItem]: очередь без указанной темы.
    """
    return [item for item in items if item.id != item_id]


def update_topic_title(
    items: list[TopicQueueItem],
    item_id: str,
    title: str,
) -> list[TopicQueueItem]:
    """Меняет формулировку темы (для pending/skipped/in_progress/published).

    Args:
        items: очередь.
        item_id: ID темы.
        title: новая формулировка.

    Returns:
        list[TopicQueueItem]: обновлённая очередь.

    Raises:
        ValueError: пустой заголовок или тема не найдена.
    """
    cleaned = title.strip()
    if not cleaned:
        raise ValueError("Тема не может быть пустой")
    found = False
    updated: list[TopicQueueItem] = []
    for item in items:
        if item.id != item_id:
            updated.append(item)
            continue
        found = True
        updated.append(
            TopicQueueItem(
                id=item.id,
                title=cleaned,
                status=item.status,
                published_at=item.published_at,
                published_post_id=item.published_post_id,
                entities=list(item.entities),
                notes=item.notes,
            )
        )
    if not found:
        raise ValueError("Тема не найдена")
    return updated


def clear_published(items: list[TopicQueueItem]) -> list[TopicQueueItem]:
    """Убирает все опубликованные темы из списка (учёт остаётся в истории постов).

    Args:
        items: очередь.

    Returns:
        list[TopicQueueItem]: очередь без published.
    """
    return [item for item in items if item.status != "published"]

def _item_from_raw(entry: object) -> TopicQueueItem | None:
    """Создаёт TopicQueueItem из сырого JSON-элемента."""
    if isinstance(entry, str):
        title = entry.strip()
        if not title:
            return None
        return TopicQueueItem(id=uuid.uuid4().hex[:12], title=title)
    if not isinstance(entry, dict):
        return None
    title = str(entry.get("title") or "").strip()
    if not title:
        return None
    status_raw = str(entry.get("status") or "pending").strip().lower()
    status: TopicStatus = (
        status_raw if status_raw in _VALID_STATUSES else "pending"  # type: ignore[assignment]
    )
    entities_raw = entry.get("entities") or []
    entities = (
        [str(e).strip() for e in entities_raw if str(e).strip()]
        if isinstance(entities_raw, list)
        else []
    )
    post_id = entry.get("published_post_id")
    published_post_id = int(post_id) if isinstance(post_id, int) else None
    item_id = str(entry.get("id") or uuid.uuid4().hex[:12])
    notes = entry.get("notes")
    return TopicQueueItem(
        id=item_id,
        title=title,
        status=status,
        published_at=str(entry["published_at"]) if entry.get("published_at") else None,
        published_post_id=published_post_id,
        entities=entities,
        notes=str(notes) if notes else None,
    )


def _normalize(text: str) -> str:
    """Нормализует формулировку для сравнения дублей."""
    lowered = text.lower().replace("ё", "е")
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return re.sub(r"\s+", " ", cleaned).strip()
