"""Роутер настроек."""

from fastapi import APIRouter

from app.api.deps import AuthDep, DbSession
from app.api.schemas.settings import SettingsResponse, SettingsUpdate
from app.domain.platform_settings import is_internal_setting_key
from app.infrastructure.ai.qwen_image_chain import exhausted_models_json
from app.repositories.setting_repository import SettingRepository
from app.services.platform_settings_service import PlatformSettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(session: DbSession, _: AuthDep) -> SettingsResponse:
    """Все настройки платформы (дефолты + БД, включая статус планировщика).

    Возвращаем полный набор (включая служебные ключи статусов планировщика и
    журнал умной публикации) — панель показывает их только для чтения.
    Редактирование служебных ключей блокируется в PATCH.
    """
    merged = await PlatformSettingsService(session).get_merged()
    merged["qwen_image_exhausted_models"] = exhausted_models_json()
    return SettingsResponse(settings=merged)


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
    repo = SettingRepository(session)
    await repo.update_many(filtered)
    await session.commit()
    merged = await PlatformSettingsService(session).get_merged()
    merged["qwen_image_exhausted_models"] = exhausted_models_json()
    return SettingsResponse(settings=merged)
