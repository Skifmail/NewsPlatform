"""Конфигурация приложения из переменных окружения."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_ENV = _BACKEND_DIR.parent / ".env"
_ENV_FILES: tuple[str, ...] = tuple(
    str(p)
    for p in (_ROOT_ENV, _BACKEND_DIR / ".env")
    if p.is_file()
)


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
    deepseek_fast_model: str = "deepseek-chat"

    # Tavily (веб-поиск для статей)
    tavily_api_key: str = ""

    # GitHub (живой Trending для отбора репозиториев в канал находок).
    # Необязателен: без токена работает с меньшим rate limit.
    github_token: str = ""

    # Telegraph (полный текст статей)
    telegraph_access_token: str = ""

    # OpenAI (optional, fallback DALL-E)
    openai_api_key: str = ""

    # Qwen-Image (DashScope) — основная генерация обложек
    qwen_image_api_key: str = ""
    qwen_image_api_base: str = (
        "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/"
        "multimodal-generation/generation"
    )
    qwen_image_model: str = "qwen-image-2.0"
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


@lru_cache
def get_settings() -> Settings:
    """Возвращает кэшированный экземпляр настроек.

    Returns:
        Settings: настройки приложения.
    """
    return Settings()
