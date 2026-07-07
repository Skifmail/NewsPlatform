"""Схемы панели использования AI и внешних API."""

from pydantic import BaseModel, Field


class QwenModelChainItem(BaseModel):
    """Статус модели в цепочке Qwen-Image."""

    model: str
    status: str
    ttl_seconds: int | None = None


class DeepSeekUsage(BaseModel):
    """Баланс DeepSeek."""

    configured: bool
    is_available: bool | None = None
    currency: str | None = None
    total_balance: str | None = None
    granted_balance: str | None = None
    topped_up_balance: str | None = None
    models: list[str] = Field(default_factory=list)
    error: str | None = None


class TavilyUsage(BaseModel):
    """Кредиты Tavily."""

    configured: bool
    current_plan: str | None = None
    key_usage: int | None = None
    key_limit: int | None = None
    plan_usage: int | None = None
    plan_limit: int | None = None
    search_usage: int | None = None
    remaining: int | None = None
    error: str | None = None


class QwenImageUsage(BaseModel):
    """Цепочка Qwen-Image и временно исчерпанные модели."""

    configured: bool
    generate_chain: list[QwenModelChainItem] = Field(default_factory=list)
    edit_chain: list[QwenModelChainItem] = Field(default_factory=list)
    exhausted_count: int = 0
    note: str = ""


class OpenAIUsage(BaseModel):
    """Статус запасного OpenAI (DALL-E)."""

    configured: bool
    note: str = ""


class LocalUsageStats(BaseModel):
    """Локальная активность платформы (не квоты провайдеров)."""

    deepseek_jobs_24h: int = 0
    deepseek_jobs_30d: int = 0
    articles_24h: int = 0
    articles_30d: int = 0
    generated_images_30d: int = 0


class AiUsageResponse(BaseModel):
    """Сводка по AI-провайдерам."""

    fetched_at: str
    cache_ttl_seconds: int
    from_cache: bool
    deepseek: DeepSeekUsage
    tavily: TavilyUsage
    qwen_image: QwenImageUsage
    openai: OpenAIUsage
    local: LocalUsageStats
