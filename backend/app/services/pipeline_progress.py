"""Детальный пошаговый прогресс пайплайна (Redis, TTL как у analytics)."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

import redis
from loguru import logger

from app.core.config import get_settings
from app.infrastructure.events import CHANNEL_UPDATES

_PROGRESS_TTL_SEC = 600
_KEY_PREFIX = "pipeline:progress:"


def _key(celery_task_id: str) -> str:
    return f"{_KEY_PREFIX}{celery_task_id}"


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def truncate_text(text: str | None, limit: int = 420) -> str | None:
    """Обрезает текст для UI без переносов."""
    if not text:
        return None
    cleaned = " ".join(str(text).split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1] + "…"


@dataclass
class PipelineEvent:
    """Один шаг или обмен данными в пайплайне."""

    id: str
    step_id: str
    label: str
    status: str = "running"  # pending | running | success | failed | skipped
    progress: int = 0
    direction: str = "internal"  # internal | outbound | inbound
    from_node: str = "platform"
    to_node: str = "platform"
    provider: str | None = None
    model: str | None = None
    request_summary: str | None = None
    response_summary: str | None = None
    started_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    duration_ms: int | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class PipelineProgress:
    """Полное состояние пайплайна одной Celery-задачи."""

    celery_task_id: str
    job_type: str = "unknown"
    label: str = "Задача"
    status: str = "running"  # running | done | error
    progress: int = 0
    current_detail: str = "Инициализация…"
    started_at: str = field(default_factory=_now_iso)
    finished_at: str | None = None
    events: list[PipelineEvent] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "events": [asdict(event) for event in self.events],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PipelineProgress:
        events = [PipelineEvent(**item) for item in data.get("events", [])]
        payload = {**data, "events": events}
        return cls(**payload)


class PipelineProgressWriter:
    """Синхронный писатель прогресса для Celery/async-сервисов."""

    def __init__(
        self,
        celery_task_id: str,
        *,
        job_type: str = "unknown",
        label: str = "Задача",
    ) -> None:
        self._celery_task_id = celery_task_id
        self._client = redis.from_url(get_settings().redis_url)
        self._state = PipelineProgress(
            celery_task_id=celery_task_id,
            job_type=job_type,
            label=label,
        )

    @property
    def celery_task_id(self) -> str:
        return self._celery_task_id

    def init(self) -> None:
        """Создаёт начальное состояние пайплайна."""
        self._state.status = "running"
        self._state.progress = 5
        self._state.current_detail = "Задача запущена…"
        self._append_internal(
            label="Старт пайплайна",
            detail=self._state.label,
            progress=5,
            status="success",
        )
        self._flush()

    def set_overview(self, detail: str, progress: int) -> None:
        """Обновляет общий прогресс и добавляет этап в журнал.

        Каждый вызов ``report_job_stage`` создаёт видимый шаг, даже если
        детальные AI-хуки ещё не сработали.
        """
        cleaned = (detail or "").strip()
        self._state.current_detail = cleaned or self._state.current_detail
        self._state.progress = max(0, min(100, progress))
        if cleaned:
            last = self._state.events[-1] if self._state.events else None
            duplicate = (
                last is not None
                and last.direction == "internal"
                and last.label == cleaned
                and last.status in {"running", "success"}
            )
            if not duplicate:
                # Предыдущий running stage → success
                if last and last.status == "running" and last.direction == "internal":
                    last.status = "success"
                    last.finished_at = _now_iso()
                    last.duration_ms = self._duration_ms(last.started_at, last.finished_at)
                event_id = uuid.uuid4().hex[:12]
                self._state.events.append(
                    PipelineEvent(
                        id=event_id,
                        step_id=event_id,
                        label=cleaned,
                        status="running",
                        progress=self._state.progress,
                        direction="internal",
                        from_node="platform",
                        to_node=_guess_stage_node(cleaned),
                        provider=_guess_stage_provider(cleaned),
                        model=_guess_stage_model(cleaned),
                    )
                )
        self._flush()

    def begin_step(
        self,
        *,
        label: str,
        from_node: str = "platform",
        to_node: str = "platform",
        provider: str | None = None,
        model: str | None = None,
        request_summary: str | None = None,
        direction: str = "outbound",
        progress: int | None = None,
        step_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Начинает шаг обмена данными; возвращает id события."""
        event_id = step_id or uuid.uuid4().hex[:12]
        event = PipelineEvent(
            id=event_id,
            step_id=event_id,
            label=label,
            status="running",
            progress=progress or self._state.progress,
            direction=direction,
            from_node=from_node,
            to_node=to_node,
            provider=provider,
            model=model,
            request_summary=truncate_text(request_summary),
            metadata=metadata,
        )
        self._state.events.append(event)
        self._state.current_detail = label
        if progress is not None:
            self._state.progress = progress
        self._flush()
        return event_id

    def complete_step(
        self,
        event_id: str,
        *,
        response_summary: str | None = None,
        metadata: dict[str, Any] | None = None,
        status: str = "success",
    ) -> None:
        """Завершает шаг успехом или пропуском."""
        event = self._find(event_id)
        if event is None:
            return
        event.status = status
        event.response_summary = truncate_text(response_summary)
        event.finished_at = _now_iso()
        event.duration_ms = self._duration_ms(event.started_at, event.finished_at)
        if metadata:
            event.metadata = {**(event.metadata or {}), **metadata}
        if status == "success":
            event.direction = "inbound" if event.direction == "outbound" else event.direction
        self._flush()

    def fail_step(self, event_id: str, error: str) -> None:
        """Помечает шаг ошибкой."""
        event = self._find(event_id)
        if event is None:
            return
        event.status = "failed"
        event.error = truncate_text(error, 500)
        event.finished_at = _now_iso()
        event.duration_ms = self._duration_ms(event.started_at, event.finished_at)
        self._state.status = "error"
        self._flush()

    def skip_step(
        self,
        *,
        label: str,
        reason: str,
        progress: int | None = None,
        to_node: str = "platform",
    ) -> None:
        """Добавляет пропущенный шаг."""
        event_id = uuid.uuid4().hex[:12]
        event = PipelineEvent(
            id=event_id,
            step_id=event_id,
            label=label,
            status="skipped",
            progress=progress or self._state.progress,
            direction="internal",
            from_node="platform",
            to_node=to_node,
            response_summary=truncate_text(reason),
            finished_at=_now_iso(),
        )
        self._state.events.append(event)
        self._state.current_detail = label
        if progress is not None:
            self._state.progress = progress
        self._flush()

    def emit_internal(
        self,
        *,
        label: str,
        detail: str | None = None,
        progress: int | None = None,
        status: str = "success",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Добавляет внутренний этап платформы."""
        self._append_internal(
            label=label,
            detail=detail,
            progress=progress,
            status=status,
            metadata=metadata,
        )
        self._flush()

    def finish(self, *, status: str = "done") -> None:
        """Завершает пайплайн."""
        for event in self._state.events:
            if event.status == "running":
                event.status = "success" if status == "done" else "failed"
                event.finished_at = _now_iso()
                event.duration_ms = self._duration_ms(event.started_at, event.finished_at)
        self._state.status = status
        self._state.finished_at = _now_iso()
        if status == "done":
            self._state.progress = 100
            self._state.current_detail = "Пайплайн завершён"
        elif status == "error":
            self._state.current_detail = "Пайплайн завершён с ошибкой"
        self._flush()

    def _append_internal(
        self,
        *,
        label: str,
        detail: str | None,
        progress: int | None,
        status: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event_id = uuid.uuid4().hex[:12]
        finished = _now_iso()
        self._state.events.append(
            PipelineEvent(
                id=event_id,
                step_id=event_id,
                label=label,
                status=status,
                progress=progress or self._state.progress,
                direction="internal",
                from_node="platform",
                to_node="platform",
                response_summary=truncate_text(detail),
                finished_at=finished,
                metadata=metadata,
            )
        )
        if detail:
            self._state.current_detail = detail
        if progress is not None:
            self._state.progress = progress

    def _find(self, event_id: str) -> PipelineEvent | None:
        for event in reversed(self._state.events):
            if event.id == event_id:
                return event
        return None

    @staticmethod
    def _duration_ms(started_at: str, finished_at: str) -> int | None:
        try:
            start = datetime.fromisoformat(started_at)
            finish = datetime.fromisoformat(finished_at)
            return max(0, int((finish - start).total_seconds() * 1000))
        except ValueError:
            return None

    def _flush(self) -> None:
        try:
            self._client.set(
                _key(self._celery_task_id),
                json.dumps(self._state.to_dict()),
                ex=_PROGRESS_TTL_SEC,
            )
            self._publish_ws()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to write pipeline progress",
                celery_task_id=self._celery_task_id,
                error=str(exc),
            )

    def _publish_ws(self) -> None:
        latest = self._state.events[-1] if self._state.events else None
        payload: dict[str, Any] = {
            "celery_task_id": self._celery_task_id,
            "job_type": self._state.job_type,
            "label": self._state.label,
            "status": self._state.status,
            "progress": self._state.progress,
            "current_detail": self._state.current_detail,
            "event_count": len(self._state.events),
        }
        if latest:
            payload["latest_event"] = asdict(latest)
        try:
            message = json.dumps({"type": "pipeline", "payload": payload})
            self._client.publish(CHANNEL_UPDATES, message)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Pipeline WS publish failed", error=str(exc))


def read_pipeline_progress(celery_task_id: str) -> dict[str, Any] | None:
    """Читает прогресс пайплайна (sync, для тестов)."""
    client = redis.from_url(get_settings().redis_url)
    raw = client.get(_key(celery_task_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def resume_or_create_writer(
    celery_task_id: str,
    *,
    job_type: str = "unknown",
    label: str = "Задача",
) -> PipelineProgressWriter:
    """Создаёт writer, подхватывая состояние из Redis при наличии."""
    writer = PipelineProgressWriter(
        celery_task_id,
        job_type=job_type,
        label=label,
    )
    existing = read_pipeline_progress(celery_task_id)
    if existing:
        try:
            writer._state = PipelineProgress.from_dict(existing)
            return writer
        except Exception:  # noqa: BLE001
            logger.warning("Failed to resume pipeline progress", celery_task_id=celery_task_id)
    writer.init()
    return writer


def _guess_stage_node(detail: str) -> str:
    lowered = detail.lower()
    if "обложк" in lowered or "image" in lowered or "gpt-image" in lowered:
        return "openai"
    if "анимац" in lowered or "video" in lowered or "grok" in lowered:
        return "openrouter"
    if "поиск" in lowered or "tavily" in lowered or "интернет" in lowered:
        return "tavily"
    if "написан" in lowered or "стать" in lowered or "тем" in lowered or "ai" in lowered:
        return "deepseek"
    return "platform"


def _guess_stage_provider(detail: str) -> str | None:
    node = _guess_stage_node(detail)
    return {
        "openai": "OpenAI",
        "openrouter": "OpenRouter / Grok",
        "tavily": "Tavily",
        "deepseek": "DeepSeek",
        "platform": "NewsPlatform",
    }.get(node)


def _guess_stage_model(detail: str) -> str | None:
    node = _guess_stage_node(detail)
    return {
        "openai": "gpt-image-2",
        "openrouter": "grok-imagine-video",
        "tavily": "search",
        "deepseek": "deepseek-chat",
    }.get(node)


async def read_pipeline_progress_async(celery_task_id: str) -> dict[str, Any] | None:
    """Читает прогресс пайплайна (async FastAPI)."""
    import redis.asyncio as aioredis

    client = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    try:
        raw = await client.get(_key(celery_task_id))
    finally:
        await client.aclose()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
