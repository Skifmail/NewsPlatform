"""Расчёт времени публикации одобренных постов по каналам."""

from datetime import UTC, datetime, timedelta

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import PostStatus
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.channel_repository import ChannelRepository
from app.repositories.processed_post_repository import ProcessedPostRepository


class SchedulingService:
    """Планирует scheduled_at для approved-постов с учётом настроек канала."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._processed = ProcessedPostRepository(session)
        self._channels = ChannelRepository(session)

    @staticmethod
    def _parse_hhmm(value: str) -> tuple[int, int]:
        """Парсит время HH:MM в UTC.

        Args:
            value: строка времени.

        Returns:
            tuple[int, int]: часы и минуты.
        """
        parts = value.strip().split(":")
        if len(parts) != 2:
            msg = f"Invalid time format: {value}"
            raise ValueError(msg)
        return int(parts[0]), int(parts[1])

    @staticmethod
    def _at_time(day: datetime, hour: int, minute: int) -> datetime:
        """Собирает datetime на ту же дату (UTC).

        Args:
            day: опорная дата.
            hour: часы.
            minute: минуты.

        Returns:
            datetime: момент времени.
        """
        return day.replace(hour=hour, minute=minute, second=0, microsecond=0)

    def _in_publish_window(self, moment: datetime, channel: Channel) -> bool:
        """Проверяет, попадает ли момент в окно публикации канала (UTC).

        Args:
            moment: проверяемый момент.
            channel: канал с настройками окна.

        Returns:
            bool: True если внутри окна.
        """
        start_h, start_m = self._parse_hhmm(channel.publish_window_start)
        end_h, end_m = self._parse_hhmm(channel.publish_window_end)
        start = self._at_time(moment, start_h, start_m)
        end = self._at_time(moment, end_h, end_m)
        if end <= start:
            return moment >= start or moment < end
        return start <= moment < end

    def _next_window_start(self, after: datetime, channel: Channel) -> datetime:
        """Ближайшее начало окна публикации не раньше after.

        Args:
            after: нижняя граница.
            channel: канал.

        Returns:
            datetime: начало окна.
        """
        start_h, start_m = self._parse_hhmm(channel.publish_window_start)
        candidate = self._at_time(after, start_h, start_m)
        if candidate < after:
            candidate += timedelta(days=1)
        return candidate

    def compute_next_slot(
        self, channel: Channel, after: datetime | None = None
    ) -> datetime:
        """Следующий слот публикации для канала.

        Args:
            channel: канал с интервалом и окном.
            after: предыдущий слот; если None — от текущего времени.

        Returns:
            datetime: UTC-время публикации.
        """
        now = datetime.now(UTC)
        interval = timedelta(minutes=max(1, channel.publish_interval_minutes))
        base = after if after and after > now else now

        if after:
            candidate = after + interval
        else:
            candidate = now + interval

        if not self._in_publish_window(candidate, channel):
            candidate = self._next_window_start(candidate, channel)
            if candidate < now:
                candidate = now
        return candidate

    async def assign_schedule_to_post(self, post: ProcessedPost) -> ProcessedPost:
        """Назначает scheduled_at посту по очереди канала.

        Args:
            post: одобренный пост.

        Returns:
            ProcessedPost: пост с заполненным scheduled_at.

        Raises:
            ValueError: канал не найден.
        """
        channel = await self._channels.get_by_id(post.channel_id)
        if not channel:
            msg = f"Channel {post.channel_id} not found"
            raise ValueError(msg)

        last = await self._processed.get_last_scheduled_for_channel(channel.id)
        slot = self.compute_next_slot(channel, after=last)
        post.scheduled_at = slot
        return await self._processed.update(post)

    async def recalculate_channel(self, channel_id: int) -> int:
        """Пересчитывает scheduled_at для всех approved постов канала.

        Args:
            channel_id: ID канала.

        Returns:
            int: число обновлённых постов.

        Raises:
            ValueError: канал не найден.
        """
        channel = await self._channels.get_by_id(channel_id)
        if not channel:
            msg = f"Channel {channel_id} not found"
            raise ValueError(msg)

        posts = await self._processed.list_approved_by_channel(channel_id)
        slot: datetime | None = None
        for post in posts:
            slot = self.compute_next_slot(channel, after=slot)
            post.scheduled_at = slot
            await self._processed.update(post)

        await self._session.commit()
        logger.info(
            "Channel schedule recalculated",
            channel_id=channel_id,
            posts=len(posts),
        )
        return len(posts)
