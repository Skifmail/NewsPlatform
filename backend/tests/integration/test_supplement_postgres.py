"""Проверки блокировок PostgreSQL; требуют отдельной тестовой БД."""

import asyncio
import importlib.util
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pytest_mock import MockerFixture
from sqlalchemy import text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.supplements import SupplementError
from app.infrastructure.database import Base
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.supplement import SupplementConfig, SupplementDraft
from app.services.supplement_service import SupplementService


@pytest.fixture
async def postgres_sessions(
    request: pytest.FixtureRequest,
) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    """Создаёт уникальную схему, не затрагивая существующие таблицы."""
    url = request.config.getoption("--supplement-postgres-url")
    if not url:
        pytest.skip(
            "Нужна отдельная тестовая PostgreSQL через --supplement-postgres-url"
        )
    schema = "supplement_test_" + uuid4().hex
    admin = create_async_engine(url)
    async with admin.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": schema}}
    )
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        async with sessions() as session:
            session.add(
                Channel(
                    id=1,
                    name="Тест",
                    platform="max",
                    platform_id="-10",
                    topic="science",
                    content_mode="article",
                )
            )
            await session.flush()
            session.add(SupplementConfig(channel_id=1, enabled=True, recipient_id=7))
            session.add(
                SupplementDraft(
                    channel_id=1,
                    slot_key="test",
                    requested_kind="fact",
                    text="Металл проводит тепло.",
                    status="awaiting",
                    review_mid="mid",
                    target_chat_id="-10",
                    sources=[{"url": "https://example.org"}],
                    image_url="local://covers/test.png",
                    image_source="generated",
                    image_prompt="Тестовая обложка",
                )
            )
            await session.commit()
        yield sessions
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


async def test_decision_when_concurrent_callbacks_should_accept_once(
    postgres_sessions: async_sessionmaker[AsyncSession], mocker: MockerFixture
) -> None:
    """Конкурирующие обработчики не принимают два решения."""
    mocker.patch(
        "app.services.supplement_service.MaxReviewClient", return_value=AsyncMock()
    )
    mocker.patch.object(
        SupplementService,
        "_image_bytes",
        new=AsyncMock(return_value=b"same-image"),
    )

    async def decide() -> str:
        async with postgres_sessions() as session:
            try:
                return await SupplementService(session).decide(
                    1, 1, 7, "mid", "approve"
                )
            except SupplementError:
                return "denied"

    assert sorted(await asyncio.gather(decide(), decide())) == ["approved", "denied"]


async def test_publish_when_concurrent_workers_should_send_once(
    postgres_sessions: async_sessionmaker[AsyncSession], mocker: MockerFixture
) -> None:
    """Блокировка и сохранённое publishing исключают повторную отправку."""
    client = AsyncMock()
    client.send.return_value = {"mid": "published", "url": "https://example.org/post"}
    mocker.patch("app.services.supplement_service.MaxReviewClient", return_value=client)
    mocker.patch.object(
        SupplementService,
        "_image_bytes",
        new=AsyncMock(return_value=b"same-image"),
    )
    async with postgres_sessions() as session:
        await SupplementService(session).decide(1, 1, 7, "mid", "approve")

    async def publish() -> None:
        async with postgres_sessions() as session:
            await SupplementService(session).publish(1)

    await asyncio.gather(publish(), publish())
    client.send.assert_awaited_once()


async def test_migration_when_reapplied_should_support_model(
    postgres_sessions: async_sessionmaker[AsyncSession], mocker: MockerFixture
) -> None:
    """Миграция создаёт совместимые с моделью таблицы и откатывается."""
    spec = importlib.util.spec_from_file_location(
        "supplement_migration",
        Path(__file__).parents[2] / "alembic/versions/048_supplement_review.py",
    )
    assert spec is not None and spec.loader is not None
    migration: Any = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    def migrate(conn: Connection) -> None:
        mocker.patch.object(
            migration, "op", Operations(MigrationContext.configure(conn))
        )
        migration.downgrade()
        migration.upgrade()

    async with postgres_sessions() as session:
        connection = await session.connection()
        await connection.run_sync(migrate)
        session.add(SupplementConfig(channel_id=1))
        await session.commit()
        assert (await session.get(SupplementConfig, 1)).enabled is False
