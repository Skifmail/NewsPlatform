"""Запись о выборе лучшей новости для умной публикации."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

CURATED_PICK_HISTORY_KEY = "curated_pick_history"
CURATED_PICK_HISTORY_LIMIT = 30

from app.domain.topics import TOPIC_LABELS


@dataclass(frozen=True)
class TopicPickResult:
    """Результат выбора материала моделью."""

    raw_post_id: int
    reason: str
    title: str
    source_name: str


@dataclass(frozen=True)
class CuratedPickRecord:
    """Элемент журнала умной публикации для панели."""

    topic: str
    topic_label: str
    raw_post_id: int
    title: str
    source_name: str
    reason: str
    candidates_count: int
    picked_at: str

    @classmethod
    def create(
        cls,
        *,
        topic: str,
        topic_label: str,
        pick: TopicPickResult,
        candidates_count: int,
        picked_at: datetime | None = None,
    ) -> "CuratedPickRecord":
        """Собирает запись журнала из результата выбора.

        Args:
            topic: код темы it | auto | russia.
            topic_label: подпись темы для UI.
            pick: выбранный материал и обоснование.
            candidates_count: число кандидатов в списке.
            picked_at: момент выбора UTC; по умолчанию — сейчас.

        Returns:
            CuratedPickRecord: готовая запись для сериализации.
        """
        moment = picked_at or datetime.now(UTC)
        return cls(
            topic=topic,
            topic_label=topic_label,
            raw_post_id=pick.raw_post_id,
            title=pick.title,
            source_name=pick.source_name,
            reason=pick.reason,
            candidates_count=candidates_count,
            picked_at=moment.isoformat(),
        )


def parse_curated_pick_history(raw: str) -> list[CuratedPickRecord]:
    """Парсит журнал выборов из JSON в settings.

    Args:
        raw: значение ключа curated_pick_history.

    Returns:
        list[CuratedPickRecord]: записи от новых к старым.
    """
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    records: list[CuratedPickRecord] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            records.append(
                CuratedPickRecord(
                    topic=str(item["topic"]),
                    topic_label=str(item.get("topic_label", item["topic"])),
                    raw_post_id=int(item["raw_post_id"]),
                    title=str(item.get("title", "")),
                    source_name=str(item.get("source_name", "")),
                    reason=str(item.get("reason", "")),
                    candidates_count=int(item.get("candidates_count", 0)),
                    picked_at=str(item.get("picked_at", "")),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return records


def serialize_curated_pick_history(records: list[CuratedPickRecord]) -> str:
    """Сериализует журнал выборов в JSON для settings.

    Args:
        records: записи от новых к старым.

    Returns:
        str: JSON-массив.
    """
    return json.dumps([asdict(record) for record in records], ensure_ascii=False)
