"""Схемы промпт-шаблонов."""

from datetime import datetime

from pydantic import BaseModel


class PromptOut(BaseModel):
    key: str
    category: str
    name: str
    description: str
    template_text: str
    template_variables: str
    channel_scope: str
    is_system_prompt: bool
    sort_order: int
    updated_at: datetime | None = None
    is_default: bool = False

    model_config = {"from_attributes": True}


class PromptCategoryOut(BaseModel):
    category: str
    label: str
    prompts: list[PromptOut]


class PromptsResponse(BaseModel):
    categories: list[PromptCategoryOut]


class PromptUpdate(BaseModel):
    template_text: str
    name: str | None = None
    description: str | None = None
