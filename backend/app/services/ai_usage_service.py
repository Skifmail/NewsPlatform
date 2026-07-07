"""Сбор данных о балансе и использовании AI-провайдеров."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import redis
from loguru import logger
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.ai_usage import (
    AiUsageResponse,
    DeepSeekUsage,
    LocalUsageStats,
    OpenAIUsage,
    QwenImageUsage,
    QwenModelChainItem,
    TavilyUsage,
)
from app.core.config import get_settings
from app.domain.enums import ImageSource, JobType
from app.infrastructure.ai.qwen_image_chain import (
    list_exhausted_models,
    resolve_edit_models,
    resolve_generate_models,
)
from app.infrastructure.models.background_job import BackgroundJob
from app.infrastructure.models.processed_post import ProcessedPost
from app.services.platform_settings_service import PlatformSettingsService

_CACHE_KEY = "ai_usage:snapshot"
_CACHE_TTL_SECONDS = 600
_TAVILY_USAGE_URL = "https://api.tavily.com/usage"


def _redis_client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url)


def _is_configured(key: str) -> bool:
    normalized = key.strip().lower()
    if not normalized:
        return False
    placeholders = {"sk-...", "sk-…", "your_api_key", "change_me", "tvly-..."}
    return normalized not in placeholders


def _build_chain_status(
    models: list[str],
    exhausted: list[dict[str, int | str]],
) -> list[QwenModelChainItem]:
    exhausted_map = {
        str(item["model"]): int(item["ttl_seconds"])
        for item in exhausted
        if int(item.get("ttl_seconds") or 0) > 0
    }
    next_assigned = False
    result: list[QwenModelChainItem] = []
    for model in models:
        ttl = exhausted_map.get(model)
        if ttl:
            result.append(
                QwenModelChainItem(model=model, status="exhausted", ttl_seconds=ttl)
            )
            continue
        if not next_assigned:
            next_assigned = True
            result.append(QwenModelChainItem(model=model, status="next"))
        else:
            result.append(QwenModelChainItem(model=model, status="available"))
    return result


async def _fetch_deepseek() -> DeepSeekUsage:
    settings = get_settings()
    key = settings.deepseek_api_key.strip()
    models = [
        name
        for name in (settings.deepseek_model, settings.deepseek_fast_model)
        if name.strip()
    ]
    if not _is_configured(key):
        return DeepSeekUsage(configured=False, models=models)

    url = f"{settings.deepseek_api_base.rstrip('/')}/user/balance"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {key}",
                    "Accept": "application/json",
                },
            )
        if response.status_code == 401:
            return DeepSeekUsage(
                configured=True,
                models=models,
                error="Неверный API-ключ DeepSeek",
            )
        if response.status_code != 200:
            return DeepSeekUsage(
                configured=True,
                models=models,
                error=f"DeepSeek API: HTTP {response.status_code}",
            )
        data = response.json()
        balance_infos = data.get("balance_infos") or []
        preferred = next(
            (item for item in balance_infos if item.get("currency") == "USD"),
            balance_infos[0] if balance_infos else None,
        )
        if not preferred:
            return DeepSeekUsage(
                configured=True,
                is_available=bool(data.get("is_available")),
                models=models,
                error="Пустой ответ balance_infos",
            )
        return DeepSeekUsage(
            configured=True,
            is_available=bool(data.get("is_available")),
            currency=str(preferred.get("currency") or ""),
            total_balance=str(preferred.get("total_balance") or ""),
            granted_balance=str(preferred.get("granted_balance") or ""),
            topped_up_balance=str(preferred.get("topped_up_balance") or ""),
            models=models,
        )
    except httpx.HTTPError as exc:
        logger.warning("DeepSeek balance fetch failed", error=str(exc))
        return DeepSeekUsage(
            configured=True,
            models=models,
            error="Не удалось связаться с DeepSeek API",
        )


async def _fetch_tavily() -> TavilyUsage:
    key = get_settings().tavily_api_key.strip()
    if not _is_configured(key):
        return TavilyUsage(configured=False)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                _TAVILY_USAGE_URL,
                headers={"Authorization": f"Bearer {key}"},
            )
        if response.status_code == 401:
            return TavilyUsage(configured=True, error="Неверный API-ключ Tavily")
        if response.status_code == 429:
            return TavilyUsage(
                configured=True,
                error="Лимит запросов /usage (10 за 10 мин) — попробуйте позже",
            )
        if response.status_code != 200:
            return TavilyUsage(
                configured=True,
                error=f"Tavily API: HTTP {response.status_code}",
            )
        data = response.json()
        account = data.get("account") or {}
        key_info = data.get("key") or {}
        plan_limit = _as_int(account.get("plan_limit"))
        plan_usage = _as_int(account.get("plan_usage"))
        remaining = (
            max(plan_limit - plan_usage, 0)
            if plan_limit is not None and plan_usage is not None
            else None
        )
        return TavilyUsage(
            configured=True,
            current_plan=str(account.get("current_plan") or "") or None,
            key_usage=_as_int(key_info.get("usage")),
            key_limit=_as_int(key_info.get("limit")),
            plan_usage=plan_usage,
            plan_limit=plan_limit,
            search_usage=_as_int(account.get("search_usage")),
            remaining=remaining,
        )
    except httpx.HTTPError as exc:
        logger.warning("Tavily usage fetch failed", error=str(exc))
        return TavilyUsage(
            configured=True,
            error="Не удалось связаться с Tavily API",
        )


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


async def _fetch_qwen_image(session: AsyncSession) -> QwenImageUsage:
    settings = get_settings()
    key = settings.qwen_image_api_key.strip()
    if not _is_configured(key):
        return QwenImageUsage(
            configured=False,
            note="QWEN_IMAGE_API_KEY не задан",
        )

    merged = await PlatformSettingsService(session).get_merged()
    generate_models = resolve_generate_models(merged.get("qwen_image_models"))
    edit_models = resolve_edit_models(merged.get("qwen_image_edit_models"))
    exhausted = list_exhausted_models()
    return QwenImageUsage(
        configured=True,
        generate_chain=_build_chain_status(generate_models, exhausted),
        edit_chain=_build_chain_status(edit_models, exhausted),
        exhausted_count=len(exhausted),
        note=(
            "DashScope не отдаёт остаток квоты по API. "
            "Показаны цепочка моделей и временно пропущенные после ошибки квоты (~6 ч)."
        ),
    )


def _fetch_openai() -> OpenAIUsage:
    configured = _is_configured(get_settings().openai_api_key)
    return OpenAIUsage(
        configured=configured,
        note=(
            "Запасной DALL-E. Остаток кредитов OpenAI через API недоступен — "
            "смотрите billing.openai.com."
            if configured
            else "OPENAI_API_KEY не задан (используется только как fallback)."
        ),
    )


async def _local_stats(session: AsyncSession) -> LocalUsageStats:
    now = datetime.now(UTC)
    day_ago = now - timedelta(days=1)
    month_ago = now - timedelta(days=30)

    async def _count_jobs(since: datetime, job_types: tuple[str, ...]) -> int:
        result = await session.execute(
            select(func.count(BackgroundJob.id)).where(
                BackgroundJob.job_type.in_(job_types),
                BackgroundJob.created_at >= since,
            )
        )
        return int(result.scalar_one())

    async def _count_articles(since: datetime) -> int:
        result = await session.execute(
            select(func.count(ProcessedPost.id)).where(
                ProcessedPost.content_mode == "article",
                ProcessedPost.created_at >= since,
            )
        )
        return int(result.scalar_one())

    async def _count_generated_images(since: datetime) -> int:
        result = await session.execute(
            select(func.count(ProcessedPost.id)).where(
                ProcessedPost.image_source == ImageSource.GENERATED.value,
                ProcessedPost.created_at >= since,
            )
        )
        return int(result.scalar_one())

    deepseek_types = (JobType.PROCESS.value, JobType.ARTICLE.value)
    return LocalUsageStats(
        deepseek_jobs_24h=await _count_jobs(day_ago, deepseek_types),
        deepseek_jobs_30d=await _count_jobs(month_ago, deepseek_types),
        articles_24h=await _count_articles(day_ago),
        articles_30d=await _count_articles(month_ago),
        generated_images_30d=await _count_generated_images(month_ago),
    )


class AiUsageService:
    """Агрегирует данные провайдеров с кэшем в Redis."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_usage(self, *, force_refresh: bool = False) -> AiUsageResponse:
        """Возвращает сводку; по умолчанию кэш 10 минут.

        Args:
            force_refresh: игнорировать кэш и запросить провайдеров заново.

        Returns:
            AiUsageResponse: балансы, кредиты и локальная статистика.
        """
        if not force_refresh:
            cached = self._read_cache()
            if cached is not None:
                return cached.model_copy(update={"from_cache": True})

        fetched_at = datetime.now(UTC).isoformat()
        payload = AiUsageResponse(
            fetched_at=fetched_at,
            cache_ttl_seconds=_CACHE_TTL_SECONDS,
            from_cache=False,
            deepseek=await _fetch_deepseek(),
            tavily=await _fetch_tavily(),
            qwen_image=await _fetch_qwen_image(self._session),
            openai=_fetch_openai(),
            local=await _local_stats(self._session),
        )
        self._write_cache(payload)
        return payload

    def _read_cache(self) -> AiUsageResponse | None:
        try:
            raw = _redis_client().get(_CACHE_KEY)
            if not raw:
                return None
            data = json.loads(raw)
            data["from_cache"] = True
            return AiUsageResponse.model_validate(data)
        except Exception as exc:
            logger.warning("AI usage cache read failed", error=str(exc))
            return None

    def _write_cache(self, payload: AiUsageResponse) -> None:
        try:
            _redis_client().setex(
                _CACHE_KEY,
                _CACHE_TTL_SECONDS,
                payload.model_dump_json(),
            )
        except Exception as exc:
            logger.warning("AI usage cache write failed", error=str(exc))
