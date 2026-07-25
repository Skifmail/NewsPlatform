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
    BalancePoint,
    DeepSeekUsage,
    LocalUsageStats,
    OpenAIUsage,
    QwenImageUsage,
    QwenModelChainItem,
    SpendHistory,
    TavilyKeyUsage,
    TavilyUsage,
)
from app.domain.ai_spend import compute_spend
from app.repositories.ai_balance_snapshot_repository import (
    AiBalanceSnapshotRepository,
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
from app.infrastructure.search.tavily_key_chain import (
    is_key_configured,
    list_exhausted_keys,
    mark_key_exhausted,
    mask_api_key,
    ordered_keys_for_use,
    parse_bool_setting,
    resolve_keys,
)
from app.infrastructure.ai.openai_key_chain import active_openai_key
from app.services.platform_settings_service import PlatformSettingsService

_CACHE_KEY = "ai_usage:snapshot"
_CACHE_TTL_SECONDS = 600
_TAVILY_USAGE_URL = "https://api.tavily.com/usage"


def _redis_client() -> redis.Redis:
    return redis.from_url(get_settings().redis_url)


def _parse_money(value: str | None) -> float | None:
    """Парсит денежную строку («1.63») во float или None."""
    if value is None:
        return None
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


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


async def _fetch_tavily_key_usage(
    key: str,
) -> tuple[
    str | None,
    int | None,
    int | None,
    int | None,
    int | None,
    int | None,
    int | None,
    str | None,
]:
    """Запрашивает /usage для одного ключа Tavily.

    Returns:
        tuple: plan, key_usage, key_limit, plan_usage, plan_limit,
            search_usage, remaining, error.
    """
    if not is_key_configured(key):
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "Некорректный API-ключ (ожидается короткий ASCII tvly-…)",
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                _TAVILY_USAGE_URL,
                headers={"Authorization": f"Bearer {key.strip()}"},
            )
        if response.status_code == 401:
            return (None, None, None, None, None, None, None, "Неверный API-ключ")
        if response.status_code == 429:
            return (
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                "Лимит запросов /usage (10 за 10 мин) — попробуйте позже",
            )
        if response.status_code != 200:
            return (
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                f"Tavily API: HTTP {response.status_code}",
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
        return (
            str(account.get("current_plan") or "") or None,
            _as_int(key_info.get("usage")),
            _as_int(key_info.get("limit")),
            plan_usage,
            plan_limit,
            _as_int(account.get("search_usage")),
            remaining,
            None,
        )
    except Exception as exc:
        logger.warning("Tavily usage fetch failed", error=str(exc))
        return (
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "Не удалось связаться с Tavily API",
        )


async def _fetch_tavily(session: AsyncSession) -> TavilyUsage:
    """Собирает usage по всем ключам Tavily и статус цепочки.

    Args:
        session: сессия БД для чтения настроек.

    Returns:
        TavilyUsage: сводка по активному ключу и списку ключей.
    """
    merged = await PlatformSettingsService(session).get_merged()
    keys = resolve_keys(merged.get("tavily_api_keys"))
    auto_switch = parse_bool_setting(merged.get("tavily_auto_switch"), True)
    active_key_id = (merged.get("tavily_active_key_id") or "").strip() or None

    if not keys:
        return TavilyUsage(configured=False, auto_switch=auto_switch)

    exhausted = list_exhausted_keys()
    exhausted_map = {
        str(item["key_id"]): int(item["ttl_seconds"])
        for item in exhausted
        if int(item.get("ttl_seconds") or 0) > 0
    }

    key_usages: list[TavilyKeyUsage] = []
    key_meta: dict[str, tuple[int | None, int | None]] = {}
    for entry in keys:
        (
            plan,
            key_usage,
            key_limit,
            plan_usage,
            plan_limit,
            search_usage,
            remaining,
            error,
        ) = await _fetch_tavily_key_usage(entry.key)
        key_meta[entry.id] = (key_usage, key_limit)

        # Проактивно помечаем ключ, если кредиты уже на нуле.
        if remaining is not None and remaining <= 0 and entry.id not in exhausted_map:
            mark_key_exhausted(entry.id)
            exhausted_map[entry.id] = max(exhausted_map.get(entry.id, 0), 1)

        ttl = exhausted_map.get(entry.id)
        if ttl:
            status = "exhausted"
        elif active_key_id and entry.id == active_key_id:
            status = "active"
        else:
            status = "available"

        key_usages.append(
            TavilyKeyUsage(
                id=entry.id,
                label=entry.label,
                source=entry.source,
                masked_key=mask_api_key(entry.key),
                status=status,
                ttl_seconds=ttl,
                current_plan=plan,
                plan_usage=plan_usage,
                plan_limit=plan_limit,
                search_usage=search_usage,
                remaining=remaining,
                error=error,
            )
        )

    next_keys = ordered_keys_for_use(
        keys,
        active_key_id=active_key_id,
        auto_switch=auto_switch,
    )
    next_id = next_keys[0].id if next_keys else None
    for item in key_usages:
        if item.status == "exhausted":
            continue
        if next_id and item.id == next_id:
            item.status = "next"
        elif item.status == "active" and next_id and item.id != next_id:
            item.status = "available"

    primary = next(
        (item for item in key_usages if item.status == "next"),
        key_usages[0],
    )
    primary_key_usage, primary_key_limit = key_meta.get(
        primary.id, (None, None)
    )

    return TavilyUsage(
        configured=True,
        auto_switch=auto_switch,
        active_key_id=active_key_id or next_id,
        current_plan=primary.current_plan,
        key_usage=primary_key_usage,
        key_limit=primary_key_limit,
        plan_usage=primary.plan_usage,
        plan_limit=primary.plan_limit,
        search_usage=primary.search_usage,
        remaining=primary.remaining,
        error=primary.error,
        keys=key_usages,
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


async def _fetch_openai(session: AsyncSession) -> OpenAIUsage:
    settings = get_settings()
    env_configured = _is_configured(settings.openai_api_key)

    merged = await PlatformSettingsService(session).get_merged()
    db_key = active_openai_key(merged.get("openai_api_keys"))
    api_key = db_key or (settings.openai_api_key.strip() if env_configured else "")

    configured = bool(api_key and _is_configured(api_key))
    if not configured:
        return OpenAIUsage(configured=False, note="Ключ OpenAI не задан")

    now = datetime.now(UTC)
    start = int((now - timedelta(days=30)).timestamp())
    end = int(now.timestamp())
    url = f"https://api.openai.com/v1/organization/costs?start_time={start}&end_time={end}&bucket_width=1d"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "application/json",
                },
            )
        if resp.status_code in (401, 403):
            return OpenAIUsage(
                configured=True,
                note="Ключ не имеет доступа к billing API — проверяйте расходы на platform.openai.com",
            )
        if resp.status_code != 200:
            return OpenAIUsage(
                configured=True,
                error=f"OpenAI API: HTTP {resp.status_code}",
            )
        data = resp.json()
        buckets = data.get("data") or []
        total = 0.0
        daily: list[dict] = []
        currency = "USD"
        for bucket in buckets:
            results = bucket.get("results") or []
            day_total = 0.0
            for r in results:
                amount = r.get("amount") or {}
                val = amount.get("value") or 0.0
                day_total += float(val)
                if amount.get("currency"):
                    currency = amount["currency"]
            total += day_total
            daily.append({
                "date": bucket.get("start_time", ""),
                "amount": round(day_total, 4),
            })
        return OpenAIUsage(
            configured=True,
            total_spent_30d=round(total, 2),
            currency=currency,
            daily_costs=daily,
        )
    except httpx.HTTPError as exc:
        logger.warning("OpenAI costs fetch failed", error=str(exc))
        return OpenAIUsage(
            configured=True,
            error="Не удалось связаться с OpenAI API",
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
        deepseek = await _fetch_deepseek()
        await self._attach_deepseek_history(deepseek)
        payload = AiUsageResponse(
            fetched_at=fetched_at,
            cache_ttl_seconds=_CACHE_TTL_SECONDS,
            from_cache=False,
            deepseek=deepseek,
            tavily=await _fetch_tavily(self._session),
            qwen_image=await _fetch_qwen_image(self._session),
            openai=await _fetch_openai(self._session),
            local=await _local_stats(self._session),
        )
        self._write_cache(payload)
        return payload

    async def snapshot_deepseek_balance(self) -> bool:
        """Снимает баланс DeepSeek для истории (для фонового планировщика).

        Returns:
            bool: True если запрос к провайдеру выполнен.
        """
        deepseek = await _fetch_deepseek()
        await self._attach_deepseek_history(deepseek)
        return deepseek.configured and not deepseek.error

    async def _attach_deepseek_history(self, deepseek: DeepSeekUsage) -> None:
        """Записывает снимок баланса DeepSeek и прикрепляет историю расходов.

        При ошибке (нет баланса/сбой БД) история остаётся None — панель
        деградирует мягко, показывая только текущий баланс.
        """
        total = _parse_money(deepseek.total_balance)
        if not deepseek.configured or deepseek.error or total is None:
            return
        try:
            repo = AiBalanceSnapshotRepository(self._session)
            await repo.record_if_changed(
                "deepseek",
                currency=deepseek.currency,
                total_balance=total,
                granted_balance=_parse_money(deepseek.granted_balance),
                topped_up_balance=_parse_money(deepseek.topped_up_balance),
            )
            await self._session.commit()
            series = await repo.series_since("deepseek", days=30)
            summary = compute_spend(series, datetime.now(UTC))
            deepseek.history = SpendHistory(
                spent_24h=summary.spent_24h,
                spent_7d=summary.spent_7d,
                spent_30d=summary.spent_30d,
                topped_up_30d=summary.topped_up_30d,
                points=[
                    BalancePoint(captured_at=ts, balance=val)
                    for ts, val in summary.points
                ],
            )
        except Exception as exc:  # noqa: BLE001 — история не критична
            logger.warning("DeepSeek spend history failed", error=str(exc))

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
