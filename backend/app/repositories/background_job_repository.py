"""Репозиторий фоновых задач."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import JobStatus
from app.infrastructure.models.background_job import BackgroundJob


class BackgroundJobRepository:
    """CRUD для background_jobs."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_celery_id(self, celery_task_id: str) -> BackgroundJob | None:
        """Находит задачу по ID Celery.

        Args:
            celery_task_id: идентификатор задачи.

        Returns:
            BackgroundJob | None: запись или None.
        """
        result = await self._session.execute(
            select(BackgroundJob).where(
                BackgroundJob.celery_task_id == celery_task_id
            )
        )
        return result.scalar_one_or_none()

    async def create(self, job: BackgroundJob) -> BackgroundJob:
        """Создаёт запись задачи.

        Args:
            job: модель.

        Returns:
            BackgroundJob: сохранённая запись.
        """
        self._session.add(job)
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def update(self, job: BackgroundJob) -> BackgroundJob:
        """Обновляет запись.

        Args:
            job: модель.

        Returns:
            BackgroundJob: обновлённая запись.
        """
        await self._session.flush()
        await self._session.refresh(job)
        return job

    async def list_non_terminal(self, limit: int = 200) -> list[BackgroundJob]:
        """Задачи в очереди или в работе (для синхронизации с Celery).

        Args:
            limit: максимум записей.

        Returns:
            list[BackgroundJob]: незавершённые задачи.
        """
        result = await self._session.execute(
            select(BackgroundJob)
            .where(
                BackgroundJob.status.in_(
                    [JobStatus.QUEUED.value, JobStatus.RUNNING.value]
                )
            )
            .order_by(BackgroundJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_recent(self, limit: int = 80) -> list[BackgroundJob]:
        """Последние задачи для панели.

        Args:
            limit: максимум записей.

        Returns:
            list[BackgroundJob]: список задач.
        """
        result = await self._session.execute(
            select(BackgroundJob)
            .order_by(BackgroundJob.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_children(self, parent_celery_task_id: str) -> list[BackgroundJob]:
        """Дочерние задачи по parent_celery_task_id.

        Args:
            parent_celery_task_id: ID родительской Celery-задачи.

        Returns:
            list[BackgroundJob]: дочерние записи.
        """
        result = await self._session.execute(
            select(BackgroundJob).where(
                BackgroundJob.parent_celery_task_id == parent_celery_task_id
            )
        )
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        """Счётчики по статусам.

        Returns:
            dict[str, int]: статус → количество.
        """
        result = await self._session.execute(
            select(BackgroundJob.status, func.count(BackgroundJob.id)).group_by(
                BackgroundJob.status
            )
        )
        return {row[0]: int(row[1]) for row in result.all()}

    async def count_active(self) -> int:
        """Число задач в очереди или в работе.

        Returns:
            int: количество активных задач.
        """
        result = await self._session.execute(
            select(func.count(BackgroundJob.id)).where(
                BackgroundJob.status.in_(
                    [JobStatus.QUEUED.value, JobStatus.RUNNING.value]
                )
            )
        )
        return int(result.scalar_one())
