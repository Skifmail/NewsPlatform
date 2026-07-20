"""Тесты сбора и синхронизации участников MAX-каналов."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.models.max_member import MaxMember
from app.infrastructure.stats.base import MemberDTO
from app.infrastructure.stats.max_stats import (
    _MESSAGE_IDS_BATCH,
    MaxStatsCollector,
    _ms_to_dt,
    parse_max_member,
)
from app.repositories.max_member_repository import MaxMemberRepository


def test_ms_to_dt_zero_and_none_are_empty() -> None:
    assert _ms_to_dt(0) is None
    assert _ms_to_dt(None) is None


def test_ms_to_dt_parses_millis() -> None:
    dt = _ms_to_dt(1784530889573)
    assert dt is not None
    assert dt.tzinfo is not None
    assert dt.year == 2026


def test_parse_max_member_full() -> None:
    raw = {
        "user_id": 8195080,
        "first_name": "Алексей",
        "last_name": "",
        "name": "Алексей",
        "is_bot": False,
        "is_admin": False,
        "is_owner": False,
        "join_time": 1784299818142,
        "last_access_time": 1784299818141,
        "last_activity_time": 1784522391000,
        "avatar_url": "https://i.oneme.ru/x",
    }
    m = parse_max_member(raw)
    assert m is not None
    assert m.user_id == 8195080
    assert m.first_name == "Алексей"
    assert m.is_bot is False
    assert m.join_at is not None and m.join_at.year == 2026
    assert m.last_activity_at is not None


def test_parse_max_member_admin_permissions() -> None:
    raw = {
        "user_id": 331140730,
        "name": "Пост Мастер",
        "is_bot": True,
        "is_admin": True,
        "permissions": ["edit", "delete", "pin_message"],
    }
    m = parse_max_member(raw)
    assert m is not None
    assert m.is_admin is True
    assert m.permissions == ["edit", "delete", "pin_message"]


def test_parse_max_member_without_user_id() -> None:
    assert parse_max_member({"name": "no id"}) is None


@pytest.mark.asyncio
async def test_post_metrics_batches_within_max_url_limit() -> None:
    """GET /messages режется на батчи ≤ лимита (иначе MAX даёт HTTP 400)."""
    # MAX отвечает 400 на слишком длинный URL (~90+ длинных mid).
    assert _MESSAGE_IDS_BATCH <= 50

    calls: list[list[str]] = []

    class _Resp:
        status = 200

        async def json(self) -> dict:
            return {"messages": []}

        async def __aenter__(self) -> "_Resp":
            return self

        async def __aexit__(self, *_: object) -> bool:
            return False

    def _get(_url: str, *, headers=None, params=None) -> "_Resp":
        calls.append(params["message_ids"].split(","))
        return _Resp()

    session = MagicMock()
    session.get = _get

    ids = [f"mid.{i:032x}" for i in range(97)]
    await MaxStatsCollector()._fetch_post_metrics(session, "tok", ids)

    assert calls, "должен быть хотя бы один запрос"
    assert all(len(chunk) <= _MESSAGE_IDS_BATCH for chunk in calls)
    assert sum(len(chunk) for chunk in calls) == 97


def _messages_session(fail_if_larger_than: int, bad_id: str | None = None):
    """Мок-сессия GET /messages: 400 если батч велик или содержит bad_id."""
    calls: list[list[str]] = []

    def _get(_url: str, *, headers=None, params=None):
        ids = params["message_ids"].split(",")
        calls.append(ids)
        too_big = len(ids) > fail_if_larger_than
        has_bad = bad_id is not None and bad_id in ids
        status = 400 if (too_big or has_bad) else 200

        class _Resp:
            def __init__(self) -> None:
                self.status = status

            async def json(self) -> dict:
                return {
                    "messages": [
                        {"body": {"mid": i}, "stat": {"views": 10}} for i in ids
                    ]
                }

            async def text(self) -> str:
                return "Invalid HTTP request"

            async def __aenter__(self):
                return self

            async def __aexit__(self, *_: object) -> bool:
                return False

        return _Resp()

    session = MagicMock()
    session.get = _get
    return session, calls


@pytest.mark.asyncio
async def test_adaptive_splits_on_oversized_batch() -> None:
    """Если MAX даёт 400 на большой батч — он дробится и всё собирается."""
    # сервер принимает максимум 10 id за запрос
    session, calls = _messages_session(fail_if_larger_than=10)
    ids = [f"mid.{i:032x}" for i in range(40)]
    metrics = await MaxStatsCollector()._collect_messages_adaptive(session, "t", ids)
    assert len(metrics) == 40  # все собраны после дробления
    assert all(len(c) <= 40 for c in calls)
    assert any(len(c) <= 10 for c in calls)  # были и мелкие успешные пачки


@pytest.mark.asyncio
async def test_adaptive_isolates_bad_id() -> None:
    """Один битый id пропускается, остальные собираются."""
    bad = "mid.deadbeef"
    session, _ = _messages_session(fail_if_larger_than=1000, bad_id=bad)
    ids = [f"mid.{i:032x}" for i in range(9)] + [bad]
    metrics = await MaxStatsCollector()._collect_messages_adaptive(session, "t", ids)
    got = {m.platform_post_id for m in metrics}
    assert bad not in got
    assert len(metrics) == 9


def _mock_session(existing: list[MaxMember]) -> tuple[MagicMock, list]:
    """Мок-сессия, отдающая existing по execute и копящая add()."""
    added: list = []
    result = MagicMock()
    result.scalars.return_value.all.return_value = existing
    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock(side_effect=added.append)
    session.flush = AsyncMock()
    return session, added


@pytest.mark.asyncio
async def test_sync_all_new() -> None:
    session, added = _mock_session([])
    repo = MaxMemberRepository(session)
    members = [
        MemberDTO(user_id=1, name="A", join_at=datetime(2026, 7, 1, tzinfo=UTC)),
        MemberDTO(user_id=2, name="B", join_at=datetime(2026, 7, 2, tzinfo=UTC)),
    ]
    res = await repo.sync_channel_members(10, members)
    assert res.new_members == 2
    assert res.left_members == 0
    assert res.total_seen == 2
    assert len(added) == 2


@pytest.mark.asyncio
async def test_sync_detects_left_and_updates_existing() -> None:
    row1 = MaxMember(channel_id=10, user_id=1, name="A", is_present=True)
    row2 = MaxMember(channel_id=10, user_id=2, name="B old", is_present=True)
    session, added = _mock_session([row1, row2])
    repo = MaxMemberRepository(session)

    # приходит только user 2 (обновлён) и новый user 3; user 1 исчез → отписался
    members = [
        MemberDTO(user_id=2, name="B new"),
        MemberDTO(user_id=3, name="C"),
    ]
    res = await repo.sync_channel_members(10, members)

    assert res.new_members == 1  # user 3
    assert res.left_members == 1  # user 1
    assert row1.is_present is False
    assert row1.left_at is not None
    assert row2.is_present is True
    assert row2.name == "B new"  # обновлён
    assert len(added) == 1


@pytest.mark.asyncio
async def test_sync_empty_is_noop() -> None:
    """Пустой ответ API не помечает всех отписавшимися."""
    row1 = MaxMember(channel_id=10, user_id=1, is_present=True)
    session, _ = _mock_session([row1])
    repo = MaxMemberRepository(session)
    res = await repo.sync_channel_members(10, [])
    assert res == type(res)(total_seen=0, new_members=0, left_members=0)
    assert row1.is_present is True
