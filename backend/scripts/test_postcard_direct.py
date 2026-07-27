#!/usr/bin/env python3
"""Прямой тест генерации открытки через gpt-image-2 (без оркестратора).

Пример:
    cd backend
    PYTHONPATH=. .venv/bin/python scripts/test_postcard_direct.py

С ключом из БД (как в проде):
    DB_HOST=localhost DB_PORT=5433 PYTHONPATH=. .venv/bin/python \
        scripts/test_postcard_direct.py --from-db

Свой текст:
    PYTHONPATH=. .venv/bin/python scripts/test_postcard_direct.py \
        --prompt "Сгенерируй открытку поздравление с днем ВМФ России"
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import get_settings
from app.infrastructure.ai.openai_key_chain import active_openai_key

DEFAULT_PROMPT = "Сгенерируй открытку поздравление с днем ВМФ России"
MODEL = "gpt-image-2"
SIZE = "1024x1024"
QUALITY = "high"
TIMEOUT_SECONDS = 180.0

_SCRIPT_DIR = Path(__file__).resolve().parent
_OUTPUT_DIR = _SCRIPT_DIR.parent / "test-output"


def _resolve_api_key(*, from_db: bool) -> str:
    """Берёт OpenAI-ключ из .env или из platform_settings в PostgreSQL."""
    if from_db:
        return asyncio.run(_load_db_key())
    key = get_settings().openai_api_key.strip()
    if not key:
        msg = (
            "OPENAI_API_KEY не задан в .env. "
            "Добавьте ключ или запустите с --from-db."
        )
        raise SystemExit(msg)
    return key


async def _load_db_key() -> str:
    from sqlalchemy import text

    from app.infrastructure.database import async_session_factory

    async with async_session_factory() as session:
        row = await session.execute(
            text("SELECT value FROM settings WHERE key = 'openai_api_keys'")
        )
        raw = row.scalar_one_or_none()
    key = active_openai_key(raw)
    if not key:
        raise SystemExit(
            "В БД нет активного OpenAI-ключа (platform_settings.openai_api_keys)."
        )
    return key


def _save_png(image_bytes: bytes, *, prompt: str) -> Path:
    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    slug = "postcard"
    for word in prompt.split()[:4]:
        cleaned = "".join(ch for ch in word.lower() if ch.isalnum())
        if cleaned:
            slug = cleaned
            break
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    path = _OUTPUT_DIR / f"{slug}-{stamp}.png"
    path.write_bytes(image_bytes)
    return path


async def generate_postcard(*, prompt: str, api_key: str) -> Path:
    """Один прямой вызов Images API — как production path для открыток."""
    print("=== Прямой тест открытки (gpt-image-2) ===")
    print(f"Промпт ({len(prompt)} символов): {prompt!r}")
    print(f"Модель: {MODEL}, size={SIZE}, quality={QUALITY}")
    print()

    async with AsyncOpenAI(
        api_key=api_key,
        timeout=TIMEOUT_SECONDS,
        max_retries=1,
    ) as client:
        response = await client.images.generate(
            model=MODEL,
            prompt=prompt,
            size=SIZE,
            quality=QUALITY,
            n=1,
        )

    usage = getattr(response, "usage", None)
    if usage is not None:
        print("=== Usage (если API вернул) ===")
        print(json.dumps(usage.model_dump(), ensure_ascii=False, indent=2))
        print()

    b64 = response.data[0].b64_json
    if not b64:
        raise SystemExit("OpenAI вернул пустой b64_json")

    image_bytes = base64.b64decode(b64, validate=True)
    out_path = _save_png(image_bytes, prompt=prompt)

    print("=== Результат ===")
    print(f"Файл: {out_path}")
    print(f"Размер: {len(image_bytes):,} байт")
    if hasattr(response, "created"):
        print(f"created: {response.created}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Прямая генерация открытки через gpt-image-2 без оркестратора.",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help=f"Текст запроса (по умолчанию: {DEFAULT_PROMPT!r})",
    )
    parser.add_argument(
        "--from-db",
        action="store_true",
        help="Взять OpenAI-ключ из platform_settings (как в проде)",
    )
    args = parser.parse_args()

    prompt = args.prompt.strip()
    if not prompt:
        raise SystemExit("Промпт не может быть пустым")

    api_key = _resolve_api_key(from_db=args.from_db)

    try:
        out_path = asyncio.run(generate_postcard(prompt=prompt, api_key=api_key))
    except Exception as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print()
    print("Откройте файл и сверьте расход в OpenAI Usage после запроса.")


if __name__ == "__main__":
    main()
