"""Роутер сводки по AI-провайдерам."""

from fastapi import APIRouter, Query

from app.api.deps import AuthDep, DbSession
from app.api.schemas.ai_usage import AiUsageResponse
from app.services.ai_usage_service import AiUsageService

router = APIRouter(prefix="/ai-usage", tags=["ai-usage"])


@router.get("", response_model=AiUsageResponse)
async def get_ai_usage(
    session: DbSession,
    _: AuthDep,
    refresh: bool = Query(
        default=False,
        description="Игнорировать кэш и запросить провайдеров заново",
    ),
) -> AiUsageResponse:
    """Баланс DeepSeek, кредиты Tavily, цепочка Qwen и локальная статистика."""
    return await AiUsageService(session).get_usage(force_refresh=refresh)
