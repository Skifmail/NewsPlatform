"""Сборка ответов API для processed_posts с данными о публикации."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.post import ProcessedPostResponse
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.publish_log_repository import PublishLogRepository


class PostResponseService:
    """Обогащает посты последней ошибкой публикации."""

    def __init__(self, session: AsyncSession) -> None:
        self._logs = PublishLogRepository(session)

    async def to_responses(
        self, posts: list[ProcessedPost]
    ) -> list[ProcessedPostResponse]:
        """Формирует список ответов с полями последней попытки публикации.

        Args:
            posts: модели processed_posts.

        Returns:
            list[ProcessedPostResponse]: ответы для API.
        """
        if not posts:
            return []
        post_ids = [post.id for post in posts]
        latest = await self._logs.map_latest_by_posts(post_ids)
        result: list[ProcessedPostResponse] = []
        for post in posts:
            base = ProcessedPostResponse.model_validate(post)
            log = latest.get(post.id)
            if log is None:
                result.append(base)
                continue
            result.append(
                base.model_copy(
                    update={
                        "last_publish_status": log.status,
                        "last_publish_error": log.error_message,
                        "last_publish_attempt_at": log.published_at,
                    }
                )
            )
        return result

    async def to_response(self, post: ProcessedPost) -> ProcessedPostResponse:
        """Формирует один ответ с данными последней попытки.

        Args:
            post: модель processed_post.

        Returns:
            ProcessedPostResponse: ответ для API.
        """
        responses = await self.to_responses([post])
        return responses[0]
