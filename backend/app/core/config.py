"""Конфигурация приложения из переменных окружения."""

import sys
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_ENV = _BACKEND_DIR.parent / ".env"
_ENV_FILES: tuple[str, ...] = tuple(
    str(p)
    for p in (_ROOT_ENV, _BACKEND_DIR / ".env")
    if p.is_file()
)

# DeepSeek с ~24.07.2026 отвечает 400 на устаревшие имена моделей
# (deepseek-chat / deepseek-reasoner). Ремапим их на актуальные с учётом роли,
# чтобы устаревший env (в т.ч. восстановленный редеплоем из панели Dokploy)
# не ронял конвейер: главная модель → pro (качество, статьи), быстрая → flash
# (дёшево, классификатор новостей).
_DEPRECATED_DEEPSEEK_MODELS: frozenset[str] = frozenset(
    {"deepseek-chat", "deepseek-reasoner"}
)
_MODEL_REPLACEMENT: dict[str, str] = {
    "deepseek_model": "deepseek-v4-pro",
    "deepseek_fast_model": "deepseek-v4-flash",
}


class Settings(BaseSettings):
    """Настройки платформы контента.

    Args:
        Нет — значения читаются из окружения и `.env`.

    Returns:
        Нет — класс настроек.

    Raises:
        ValidationError: при невалидных обязательных полях.
    """

    model_config = SettingsConfigDict(
        env_file=_ENV_FILES or ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    db_user: str = "postgres"
    db_password: str = "postgres"
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "content_platform"
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/content_platform"
    )
    database_url_sync: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/content_platform"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_api_base: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-v4-pro"
    deepseek_fast_model: str = "deepseek-v4-flash"

    # Tavily (веб-поиск для статей)
    tavily_api_key: str = ""

    # GitHub (живой Trending для отбора репозиториев в канал находок).
    # Необязателен: без токена работает с меньшим rate limit.
    github_token: str = ""

    # Telegraph (полный текст статей)
    telegraph_access_token: str = ""

    # OpenAI (optional, gpt-image-2)
    openai_api_key: str = ""

    # Qwen-Image (DashScope) — основная генерация обложек
    qwen_image_api_key: str = ""
    qwen_image_api_base: str = (
        "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/"
        "multimodal-generation/generation"
    )
    qwen_image_model: str = ""
    qwen_image_models: str = ""
    qwen_image_edit_models: str = ""
    qwen_image_size: str = "1024*1024"

    # Telegram
    telegram_bot_token: str = ""
    telegram_api_id: int = 0
    telegram_api_hash: str = ""
    telegram_phone: str = ""

    # VK
    vk_access_token: str = ""
    # Пользовательский токен VK с правами photos+wall+groups (нужен для загрузки фото).
    # Если не задан — фото публикуются без картинки.
    vk_user_token: str = ""
    # VK ID приложение для OAuth (Authorization Code flow).
    vk_app_client_id: str = "54690770"
    vk_app_client_secret: str = ""

    # MAX (мессенджер) — токен бота из business.max.ru
    max_bot_token: str = ""
    # Базовый URL Bot API MAX. С 19.07.2025 платформа мигрирует на platform-api2.
    max_api_base: str = "https://platform-api2.max.ru"
    # Путь к PEM-бандлу доверенных CA Минцифры (Russian Trusted Root/Sub CA),
    # которыми подписан сертификат platform-api2.max.ru. Пусто = встроенный бандл.
    max_ca_bundle: str = ""

    # VK API
    vk_api_version: str = "5.199"

    # Alert bot
    alert_bot_token: str = ""
    alert_chat_id: str = ""

    # App / панель управления
    secret_key: str = "change_me"
    admin_username: str = "admin"
    admin_password: str = "admin"
    debug: bool = False
    log_level: str = "INFO"
    retention_days: int = 30
    # Парсинг: 1 = только вчера и сегодня (UTC) по published_at
    fetch_max_age_days: int = 1
    # CORS: через запятую, напр. https://panel.example.com
    cors_origins: str = ""

    @field_validator("telegram_api_id", mode="before")
    @classmethod
    def _empty_telegram_api_id_to_zero(cls, value: object) -> object:
        """Пустая строка в .env трактуется как «не задано»."""
        if value == "" or value is None:
            return 0
        return value

    @model_validator(mode="after")
    def _remap_deprecated_models(self) -> "Settings":
        """Заменяет устаревшие имена моделей DeepSeek на актуальные.

        DeepSeek удалил `deepseek-chat`/`deepseek-reasoner` — вызовы с ними
        падают 400 и останавливают весь конвейер. Ремап делает конфиг
        самовосстанавливающимся, если такой env вернётся.

        Returns:
            Settings: настройки с валидными именами моделей.
        """
        for attr, replacement in _MODEL_REPLACEMENT.items():
            current = getattr(self, attr)
            if current in _DEPRECATED_DEEPSEEK_MODELS:
                print(
                    f"[config] Устаревшая модель DeepSeek '{current}' "
                    f"заменена на '{replacement}' ({attr})",
                    file=sys.stderr,
                )
                object.__setattr__(self, attr, replacement)
        return self


@lru_cache
def get_settings() -> Settings:
    """Возвращает кэшированный экземпляр настроек.

    Returns:
        Settings: настройки приложения.
    """
    return Settings()
