"""Репозиторий промпт-шаблонов."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.models.prompt_template import PromptTemplate


class PromptTemplateRepository:
    """CRUD для prompt_templates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_all(self) -> list[PromptTemplate]:
        result = await self._session.execute(
            select(PromptTemplate).order_by(
                PromptTemplate.category, PromptTemplate.sort_order
            )
        )
        return list(result.scalars().all())

    async def get_by_key(self, key: str) -> PromptTemplate | None:
        result = await self._session.execute(
            select(PromptTemplate).where(PromptTemplate.key == key)
        )
        return result.scalar_one_or_none()

    async def get_by_category(self, category: str) -> list[PromptTemplate]:
        result = await self._session.execute(
            select(PromptTemplate)
            .where(PromptTemplate.category == category)
            .order_by(PromptTemplate.sort_order)
        )
        return list(result.scalars().all())

    async def update(
        self,
        key: str,
        template_text: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> PromptTemplate | None:
        prompt = await self.get_by_key(key)
        if prompt is None:
            return None
        prompt.template_text = template_text
        if name is not None:
            prompt.name = name
        if description is not None:
            prompt.description = description
        await self._session.flush()
        return prompt
