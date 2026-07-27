"""Базовый интерфейс публикатора."""

from abc import ABC, abstractmethod

from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost


class BasePublisher(ABC):
    """Абстрактный публикатор на платформу."""

    @abstractmethod
    async def publish(
        self,
        post: ProcessedPost,
        channel: Channel,
        image_bytes: bytes | None,
        video_bytes: bytes | None = None,
    ) -> str:
        """Публикует пост.

        Args:
            post: обработанный пост.
            channel: канал.
            image_bytes: байты изображения.

        Returns:
            str: ID поста на платформе.

        Raises:
            RuntimeError: при ошибке публикации.
        """
