"""Loguru-sink, сохраняющий ошибки/предупреждения в таблицу app_error_logs.

Работает синхронно (psycopg2 через database_url_sync), чтобы одинаково
перехватывать логи и в backend (async), и в Celery-воркере/бите. Любой сбой
самого сохранения глушится в stderr — логирование приложения не должно падать.
"""

import sys
import threading
from datetime import UTC

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings

# Уровни, которые попадают в окно диагностики. WARNING включён намеренно:
# многие «тихие» сбои (публикация, статистика, обрезка ответа) логируются как WARNING.
_CAPTURED_LEVELS = frozenset({"WARNING", "ERROR", "CRITICAL"})

_INSERT = text(
    "INSERT INTO app_error_logs "
    "(created_at, level, service, source, message, context) "
    "VALUES (:created_at, :level, :service, :source, :message, :context)"
)

_engine: Engine | None = None
_engine_lock = threading.Lock()
_registered = False
_reentrancy = threading.local()


def _detect_service() -> str:
    """Определяет, из какого процесса пишется лог (worker/beat/backend)."""
    argv = " ".join(sys.argv).lower()
    if "beat" in argv:
        return "beat"
    if "celery" in argv or "worker" in argv:
        return "worker"
    return "backend"


_SERVICE = _detect_service()


def _get_engine() -> Engine:
    """Ленивая инициализация синхронного engine (одно соединение)."""
    global _engine
    if _engine is None:
        with _engine_lock:
            if _engine is None:
                _engine = create_engine(
                    get_settings().database_url_sync,
                    pool_pre_ping=True,
                    pool_size=1,
                    max_overflow=2,
                    pool_recycle=1800,
                )
    return _engine


def _emit_to_db(message: object) -> None:
    """Loguru-sink: сохраняет запись в БД. Никогда не бросает исключений."""
    if getattr(_reentrancy, "active", False):
        return
    try:
        record = message.record  # type: ignore[attr-defined]
        level = record["level"].name
        if level not in _CAPTURED_LEVELS:
            return
        created_at = record["time"].astimezone(UTC)
        source = f"{record['name']}:{record['function']}:{record['line']}"[:512]
        text_message = str(record["message"])[:8000]
        exc = record.get("exception")
        context: str | None = None
        if exc is not None:
            import traceback

            context = "".join(
                traceback.format_exception(exc.type, exc.value, exc.traceback)
            )[:8000]

        _reentrancy.active = True
        with _get_engine().begin() as conn:
            conn.execute(
                _INSERT,
                {
                    "created_at": created_at,
                    "level": level,
                    "service": _SERVICE,
                    "source": source,
                    "message": text_message,
                    "context": context,
                },
            )
    except Exception as exc:  # noqa: BLE001 — sink обязан быть «немым»
        print(f"[error_log_sink] не удалось сохранить лог: {exc}", file=sys.stderr)
    finally:
        _reentrancy.active = False


def register_db_error_sink() -> None:
    """Идемпотентно подключает БД-sink к loguru (WARNING и выше)."""
    global _registered
    if _registered:
        return
    from loguru import logger

    logger.add(_emit_to_db, level="WARNING", enqueue=False, catch=True)
    _registered = True
