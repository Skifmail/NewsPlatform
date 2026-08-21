"""Репозиторий участников MAX-каналов: синхронизация и агрегаты аналитики."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.max_member import MaxMember
from app.infrastructure.stats.base import MemberDTO


@dataclass(frozen=True)
class MemberSyncResult:
    """Итог синхронизации списка участников."""

    total_seen: int
    new_members: int
    left_members: int


class MaxMemberRepository:
    """CRUD и аналитические выборки по участникам MAX-каналов."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def sync_channel_members(
        self, channel_id: int, members: list[MemberDTO]
    ) -> MemberSyncResult:
        """Синхронизирует список участников канала.

        Обновляет присутствующих, добавляет новых и помечает исчезнувших
        как отписавшихся (``is_present=False`` + ``left_at``). Пустой список
        игнорируется (защита от временной недоступности API — не считаем,
        что все отписались).

        Args:
            channel_id: ID канала.
            members: актуальный список участников от API.

        Returns:
            MemberSyncResult: сколько всего, новых и отписавшихся.
        """
        if not members:
            return MemberSyncResult(total_seen=0, new_members=0, left_members=0)

        now = datetime.now(UTC)
        existing_rows = (
            (
                await self._session.execute(
                    select(MaxMember).where(MaxMember.channel_id == channel_id)
                )
            )
            .scalars()
            .all()
        )
        by_user = {row.user_id: row for row in existing_rows}
        incoming_ids = {m.user_id for m in members}

        new_members = 0
        for dto in members:
            row = by_user.get(dto.user_id)
            if row is None:
                self._session.add(_dto_to_model(channel_id, dto, now))
                new_members += 1
            else:
                _apply_dto(row, dto, now)

        left_members = 0
        for row in existing_rows:
            if row.user_id not in incoming_ids and row.is_present:
                row.is_present = False
                row.left_at = now
                left_members += 1

        await self._session.flush()
        return MemberSyncResult(
            total_seen=len(incoming_ids),
            new_members=new_members,
            left_members=left_members,
        )

    async def count_present(
        self, channel_id: int, *, include_bots: bool = False
    ) -> int:
        """Текущее число присутствующих участников."""
        stmt = select(func.count(MaxMember.id)).where(
            MaxMember.channel_id == channel_id,
            MaxMember.is_present.is_(True),
        )
        if not include_bots:
            stmt = stmt.where(MaxMember.is_bot.is_(False))
        return int((await self._session.execute(stmt)).scalar_one())

    async def count_joined_since(self, channel_id: int, since: datetime) -> int:
        """Сколько присоединилось с момента ``since`` (по join_at)."""
        stmt = select(func.count(MaxMember.id)).where(
            MaxMember.channel_id == channel_id,
            MaxMember.is_bot.is_(False),
            MaxMember.join_at.isnot(None),
            MaxMember.join_at >= since,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def count_left_since(self, channel_id: int, since: datetime) -> int:
        """Сколько отписалось с момента ``since`` (по left_at)."""
        stmt = select(func.count(MaxMember.id)).where(
            MaxMember.channel_id == channel_id,
            MaxMember.is_bot.is_(False),
            MaxMember.left_at.isnot(None),
            MaxMember.left_at >= since,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def count_active_since(
        self, channel_id: int, since: datetime, *, by: str = "access"
    ) -> int:
        """Сколько участников были активны с момента ``since``.

        Args:
            channel_id: ID канала.
            since: нижняя граница окна.
            by: ``access`` (открывали канал, last_access_at) или
                ``activity`` (были онлайн в MAX, last_activity_at).

        Returns:
            int: число активных присутствующих участников.
        """
        column = (
            MaxMember.last_access_at if by == "access" else MaxMember.last_activity_at
        )
        stmt = select(func.count(MaxMember.id)).where(
            MaxMember.channel_id == channel_id,
            MaxMember.is_bot.is_(False),
            MaxMember.is_present.is_(True),
            column.isnot(None),
            column >= since,
        )
        return int((await self._session.execute(stmt)).scalar_one())

    async def joins_by_day(
        self, channel_id: int, since: datetime
    ) -> list[tuple[str, int]]:
        """Гистограмма вступлений по дням с момента ``since``.

        Returns:
            list[tuple[str, int]]: (YYYY-MM-DD, количество) от старых к новым.
        """
        day = func.date_trunc("day", MaxMember.join_at)
        stmt = (
            select(day.label("d"), func.count(MaxMember.id))
            .where(
                MaxMember.channel_id == channel_id,
                MaxMember.is_bot.is_(False),
                MaxMember.join_at.isnot(None),
                MaxMember.join_at >= since,
            )
            .group_by(day)
            .order_by(day)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(d.date().isoformat(), int(count)) for d, count in rows]

    async def leaves_by_day(
        self, channel_id: int, since: datetime
    ) -> list[tuple[str, int]]:
        """Гистограмма отписок по дням с момента ``since``."""
        day = func.date_trunc("day", MaxMember.left_at)
        stmt = (
            select(day.label("d"), func.count(MaxMember.id))
            .where(
                MaxMember.channel_id == channel_id,
                MaxMember.is_bot.is_(False),
                MaxMember.left_at.isnot(None),
                MaxMember.left_at >= since,
            )
            .group_by(day)
            .order_by(day)
        )
        rows = (await self._session.execute(stmt)).all()
        return [(d.date().isoformat(), int(count)) for d, count in rows]

    async def list_members(
        self,
        channel_id: int,
        *,
        present_only: bool = True,
        include_bots: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[MaxMember]:
        """Список участников канала (новые сверху по join_at)."""
        stmt = select(MaxMember).where(MaxMember.channel_id == channel_id)
        if present_only:
            stmt = stmt.where(MaxMember.is_present.is_(True))
        if not include_bots:
            stmt = stmt.where(MaxMember.is_bot.is_(False))
        stmt = stmt.order_by(MaxMember.join_at.desc().nullslast()).limit(limit).offset(offset)
        return list((await self._session.execute(stmt)).scalars().all())


def _dto_to_model(channel_id: int, dto: MemberDTO, now: datetime) -> MaxMember:
    """Создаёт новую запись участника из DTO."""
    return MaxMember(
        channel_id=channel_id,
        user_id=dto.user_id,
        first_name=dto.first_name,
        last_name=dto.last_name,
        name=dto.name,
        username=dto.username,
        avatar_url=dto.avatar_url,
        is_bot=dto.is_bot,
        is_admin=dto.is_admin,
        is_owner=dto.is_owner,
        permissions=",".join(dto.permissions) if dto.permissions else None,
        join_at=dto.join_at,
        last_access_at=dto.last_access_at,
        last_activity_at=dto.last_activity_at,
        is_present=True,
        left_at=None,
        last_synced_at=now,
    )


def _apply_dto(row: MaxMember, dto: MemberDTO, now: datetime) -> None:
    """Обновляет существующую запись данными из DTO."""
    row.first_name = dto.first_name
    row.last_name = dto.last_name
    row.name = dto.name
    row.username = dto.username
    row.avatar_url = dto.avatar_url
    row.is_bot = dto.is_bot
    row.is_admin = dto.is_admin
    row.is_owner = dto.is_owner
    row.permissions = ",".join(dto.permissions) if dto.permissions else None
    if dto.join_at is not None:
        row.join_at = dto.join_at
    if dto.last_access_at is not None:
        row.last_access_at = dto.last_access_at
    if dto.last_activity_at is not None:
        row.last_activity_at = dto.last_activity_at
    row.is_present = True
    row.left_at = None
    row.last_synced_at = now
