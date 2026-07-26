"""Сервис промпт-шаблонов.

Importers:
  - process_service.py, curated_publish_service.py, article_generation_service.py
    (оркестраторы загружают промпты через get())
  - api/routers/prompts.py (CRUD эндпоинты)
Affected API: GET/PATCH /api/prompts, POST /api/prompts/{key}/reset
Data schema: PromptTemplate model ↔ PromptTemplateRepository
User instruction: "не нужно ничего захардкоживать — пусть падает с понятной ошибкой"
"""

from collections import defaultdict

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.prompt_defaults import (
    CATEGORY_LABELS,
    CATEGORY_ORDER,
    PROMPT_DEFAULTS,
)
from app.domain.prompt_errors import PromptNotFoundError
from app.infrastructure.models.prompt_template import PromptTemplate
from app.repositories.prompt_template_repository import PromptTemplateRepository


class PromptService:
    """Загрузка, обновление и сброс промпт-шаблонов."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = PromptTemplateRepository(session)
        self._session = session

    async def get(self, key: str) -> str:
        prompt = await self._repo.get_by_key(key)
        if prompt is None:
            raise PromptNotFoundError(key)
        return prompt.template_text

    async def get_template(self, key: str) -> PromptTemplate:
        prompt = await self._repo.get_by_key(key)
        if prompt is None:
            raise PromptNotFoundError(key)
        return prompt

    async def get_all_grouped(self) -> list[dict]:
        all_prompts = await self._repo.get_all()
        by_category: dict[str, list[PromptTemplate]] = defaultdict(list)
        for p in all_prompts:
            by_category[p.category].append(p)

        result = []
        seen = set()
        for cat in CATEGORY_ORDER:
            if cat in by_category:
                result.append(
                    {
                        "category": cat,
                        "label": CATEGORY_LABELS.get(cat, cat),
                        "prompts": by_category[cat],
                    }
                )
                seen.add(cat)
        for cat in sorted(by_category.keys() - seen):
            result.append(
                {
                    "category": cat,
                    "label": CATEGORY_LABELS.get(cat, cat),
                    "prompts": by_category[cat],
                }
            )
        return result

    async def update(
        self,
        key: str,
        template_text: str,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> PromptTemplate:
        prompt = await self._repo.update(
            key, template_text, name=name, description=description
        )
        if prompt is None:
            raise PromptNotFoundError(key)
        await self._session.commit()
        return prompt

    async def reset(self, key: str) -> PromptTemplate:
        default = PROMPT_DEFAULTS.get(key)
        if default is None:
            raise PromptNotFoundError(key)
        prompt = await self._repo.update(key, default.template_text)
        if prompt is None:
            raise PromptNotFoundError(key)
        await self._session.commit()
        return prompt
