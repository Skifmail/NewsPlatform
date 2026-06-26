"""Обновление изображения поста из источника."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.ai.image_service import ImageService
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.services.platform_settings_service import PlatformSettingsService


class ImageRefreshService:
    """Подтягивает картинку из raw_post или страницы новости."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._processed = ProcessedPostRepository(session)

    async def refresh_from_source(self, post_id: int) -> ProcessedPost:
        """Заполняет generated_image_url из оригинала.

        Args:
            post_id: ID processed_post.

        Returns:
            ProcessedPost: обновлённый пост.

        Raises:
            ValueError: пост или raw_post не найден, картинка не найдена.
        """
        post = await self._processed.get_by_id(post_id)
        if not post or not post.raw_post or not post.channel:
            msg = f"Post {post_id} not found"
            raise ValueError(msg)

        platform_settings = await PlatformSettingsService(self._session).get_merged()
        images = ImageService.from_settings_dict(platform_settings)
        image_url, image_source = await images.resolve_image(
            post.raw_post,
            post.channel,
            generate_if_missing=ImageService.ai_generation_available(),
        )
        if not image_url:
            msg = "Изображение в источнике не найдено и AI-генерация не удалась"
            raise ValueError(msg)

        post.generated_image_url = image_url
        post.image_source = image_source
        updated = await self._processed.update(post)
        await self._session.commit()
        return updated
