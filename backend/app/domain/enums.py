"""Доменные перечисления платформы."""

from enum import StrEnum


class Topic(StrEnum):
    """Тематика контента."""

    IT = "it"
    AUTO = "auto"
    RUSSIA = "russia"
    SPORT = "sport"


class SourceType(StrEnum):
    """Тип источника."""

    RSS = "rss"
    TELEGRAM = "telegram"
    WEB = "web"


class Platform(StrEnum):
    """Платформа публикации."""

    TELEGRAM = "telegram"
    VK = "vk"
    MAX = "max"


class PostStatus(StrEnum):
    """Статус обработанного поста."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    FAILED = "failed"


class ImageSource(StrEnum):
    """Источник изображения поста."""

    ORIGINAL = "original"
    GENERATED = "generated"
    MANUAL = "manual"
    NONE = "none"


class PublishStatus(StrEnum):
    """Статус записи в логе публикации."""

    SUCCESS = "success"
    FAILED = "failed"


class JobType(StrEnum):
    """Тип фоновой задачи Celery."""

    FETCH = "fetch"
    PROCESS = "process"
    PUBLISH = "publish"
    ARTICLE = "article"


class ContentMode(StrEnum):
    """Режим контента канала / поста."""

    NEWS = "news"
    ARTICLE = "article"


class JobStatus(StrEnum):
    """Статус фоновой задачи."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
