"""Схемы панели использования AI и внешних API."""

from pydantic import BaseModel, Field


class QwenModelChainItem(BaseModel):
    """Статус модели в цепочке Qwen-Image."""

    model: str
    status: str
    ttl_seconds: int | None = None


class BalancePoint(BaseModel):
    """Точка истории баланса."""

    captured_at: str
    balance: float


class SpendHistory(BaseModel):
    """История расходов провайдера из снимков баланса."""

    spent_24h: float = 0.0
    spent_7d: float = 0.0
    spent_30d: float = 0.0
    topped_up_30d: float = 0.0
    points: list[BalancePoint] = Field(default_factory=list)


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
    history: SpendHistory | None = None


class TavilyKeyUsage(BaseModel):
    """Использование одного ключа Tavily."""

    id: str
    label: str
    source: str
    masked_key: str
    status: str
    ttl_seconds: int | None = None
    current_plan: str | None = None
    plan_usage: int | None = None
    plan_limit: int | None = None
    search_usage: int | None = None
    remaining: int | None = None
    error: str | None = None


class TavilyUsage(BaseModel):
    """Кредиты Tavily (активный ключ + цепочка)."""

    configured: bool
    auto_switch: bool = True
    active_key_id: str | None = None
    current_plan: str | None = None
    key_usage: int | None = None
    key_limit: int | None = None
    plan_usage: int | None = None
    plan_limit: int | None = None
    search_usage: int | None = None
    remaining: int | None = None
    error: str | None = None
    keys: list[TavilyKeyUsage] = Field(default_factory=list)


class QwenImageUsage(BaseModel):
    """Цепочка Qwen-Image и временно исчерпанные модели."""

    configured: bool
    generate_chain: list[QwenModelChainItem] = Field(default_factory=list)
    edit_chain: list[QwenModelChainItem] = Field(default_factory=list)
    exhausted_count: int = 0
    note: str = ""


class OpenAIUsage(BaseModel):
    """Статус OpenAI (gpt-image-2)."""

    configured: bool
    total_spent_30d: float | None = None
    currency: str | None = None
    daily_costs: list[dict] | None = None
    error: str | None = None
    note: str = ""


class OpenRouterUsage(BaseModel):
    """Баланс и usage OpenRouter (Grok Imagine Video)."""

    configured: bool
    remaining: float | None = None
    total_credits: float | None = None
    total_usage: float | None = None
    key_label: str | None = None
    key_usage: float | None = None
    key_usage_daily: float | None = None
    key_usage_monthly: float | None = None
    limit_remaining: float | None = None
    limit: float | None = None
    is_free_tier: bool | None = None
    error: str | None = None
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
    openrouter: OpenRouterUsage
    local: LocalUsageStats
