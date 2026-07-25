"""Роутер настроек."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException

from app.api.deps import AuthDep, DbSession
from app.api.schemas.settings import SettingsResponse, SettingsUpdate
from app.domain.platform_settings import is_internal_setting_key
from app.infrastructure.ai.qwen_image_chain import exhausted_models_json
from app.infrastructure.ai.openai_key_chain import (
    mask_openai_keys_json,
    merge_openai_keys_on_update,
)
from app.infrastructure.search.tavily_key_chain import (
    clear_key_exhausted,
    mask_api_key,
    mask_keys_json,
    merge_keys_on_update,
    resolve_keys,
)
from app.repositories.setting_repository import SettingRepository
from app.services.platform_settings_service import PlatformSettingsService

router = APIRouter(prefix="/settings", tags=["settings"])

_AI_USAGE_CACHE_KEY = "ai_usage:snapshot"


def _invalidate_ai_usage_cache() -> None:
    """Сбрасывает кэш /ai-usage после смены ключей Tavily."""
    try:
        import redis

        from app.core.config import get_settings

        redis.from_url(get_settings().redis_url).delete(_AI_USAGE_CACHE_KEY)
    except Exception:
        pass


def _public_settings(merged: dict[str, str]) -> dict[str, str]:
    """Готовит настройки для панели: маскирует секреты Tavily.

    Args:
        merged: полные настройки дефолты + БД.

    Returns:
        dict[str, str]: безопасный снимок для GET/PATCH ответа.
    """
    public = dict(merged)
    public["qwen_image_exhausted_models"] = exhausted_models_json()
    public["tavily_api_keys"] = mask_keys_json(merged.get("tavily_api_keys"))
    public["openai_api_keys"] = mask_openai_keys_json(merged.get("openai_api_keys"))

    resolved = [
        {
            "id": item.id,
            "label": item.label,
            "key": mask_api_key(item.key),
            "source": item.source,
        }
        for item in resolve_keys(merged.get("tavily_api_keys"))
    ]
    public["tavily_keys_resolved"] = json.dumps(resolved, ensure_ascii=False)
    return public


@router.get("", response_model=SettingsResponse)
async def get_settings(session: DbSession, _: AuthDep) -> SettingsResponse:
    """Все настройки платформы (дефолты + БД, включая статус планировщика).

    Возвращаем полный набор (включая служебные ключи статусов планировщика и
    журнал умной публикации) — панель показывает их только для чтения.
    Редактирование служебных ключей блокируется в PATCH.
    """
    merged = await PlatformSettingsService(session).get_merged()
    return SettingsResponse(settings=_public_settings(merged))


@router.patch("", response_model=SettingsResponse)
async def update_settings(
    data: SettingsUpdate, session: DbSession, _: AuthDep
) -> SettingsResponse:
    """Обновляет настройки (тогглы автоматики, промпты, интервалы)."""
    filtered = {
        key: value
        for key, value in data.settings.items()
        if not is_internal_setting_key(key)
    }
    # Служебные/вычисляемые поля только для GET — не сохраняем.
    filtered.pop("tavily_keys_resolved", None)
    filtered.pop("qwen_image_exhausted_models", None)

    repo = SettingRepository(session)

    if "openai_api_keys" in filtered:
        previous_openai = await repo.get("openai_api_keys", "[]")
        try:
            filtered["openai_api_keys"] = merge_openai_keys_on_update(
                previous_raw=previous_openai,
                incoming_raw=filtered["openai_api_keys"],
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if "tavily_api_keys" in filtered:
        previous = await repo.get("tavily_api_keys", "[]")
        try:
            filtered["tavily_api_keys"] = merge_keys_on_update(
                previous_raw=previous,
                incoming_raw=filtered["tavily_api_keys"],
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    if "tavily_active_key_id" in filtered:
        active_id = filtered["tavily_active_key_id"].strip()
        if active_id:
            clear_key_exhausted(active_id)

    tavily_touched = any(
        key in filtered
        for key in (
            "tavily_api_keys",
            "tavily_active_key_id",
            "tavily_auto_switch",
        )
    )

    await repo.update_many(filtered)
    await session.commit()
    if tavily_touched:
        _invalidate_ai_usage_cache()
    merged = await PlatformSettingsService(session).get_merged()
    return SettingsResponse(settings=_public_settings(merged))
