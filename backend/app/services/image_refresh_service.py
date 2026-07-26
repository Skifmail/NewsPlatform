"""Обновление изображения поста из источника."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.ai.image_service import ImageGenPrompts, ImageService
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.processed_post_repository import ProcessedPostRepository
from app.services.platform_settings_service import PlatformSettingsService
from app.services.prompt_service import PromptService


class ImageRefreshService:
    """Подтягивает картинку из raw_post или страницы новости."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._processed = ProcessedPostRepository(session)
        self._prompts = PromptService(session)

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
        image_prompts = ImageGenPrompts(
            no_text_negative=await self._prompts.get("negative.qwen_no_text"),
            news_negative=await self._prompts.get("negative.qwen_news"),
            cover_template=await self._prompts.get("image.cover_prompt"),
            postcard_cover_template=await self._prompts.get(
                "image.cover_prompt_postcard"
            ),
        )
        images = ImageService.from_settings_dict(
            platform_settings, prompts=image_prompts
        )
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
