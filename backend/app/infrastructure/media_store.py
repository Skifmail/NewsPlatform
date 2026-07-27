"""Локальное хранилище сгенерированных изображений на общем volume.

Композитинг обложки (логотип на фоне) и публикация поста выполняются в
разных celery-контейнерах (см. очереди 'ai' и 'celery' в celery_app.py).
Чтобы передать готовый JPEG между процессами без лишнего HTTP-круга,
файл кладётся на общий docker volume, а вместо HTTP-URL в БД сохраняется
схема ``local://<relative_path>`` — её понимает download_and_resize.
"""

import uuid
from pathlib import Path

MEDIA_ROOT = Path("/app/media")
_LOCAL_SCHEME = "local://"


def save_media(data: bytes, subdir: str, suffix: str = ".jpg") -> str:
    """Сохраняет байты на общий volume и возвращает local:// ссылку.

    Args:
        data: содержимое файла.
        subdir: подпапка внутри MEDIA_ROOT (например, "covers").
        suffix: расширение файла.

    Returns:
        str: ссылка вида local://covers/<uuid>.jpg.
    """
    directory = MEDIA_ROOT / subdir
    directory.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{suffix}"
    (directory / filename).write_bytes(data)
    return f"{_LOCAL_SCHEME}{subdir}/{filename}"


def is_local_media_url(url: str) -> bool:
    """Проверяет, что ссылка указывает на файл на общем volume."""
    return url.startswith(_LOCAL_SCHEME)


def read_media(url: str) -> bytes | None:
    """Читает файл по local:// ссылке.

    Args:
        url: ссылка вида local://covers/<uuid>.jpg.

    Returns:
        bytes | None: содержимое файла или None, если не найден.
    """
    if not is_local_media_url(url):
        return None
    relative = url.removeprefix(_LOCAL_SCHEME)
    path = MEDIA_ROOT / relative
    try:
        return path.read_bytes()
    except OSError:
        return None


def public_media_url(url: str | None) -> str | None:
    """Convert ``local://`` storage URL to browser-accessible API path."""
    if not url:
        return None
    if is_local_media_url(url):
        return f"/api/media/{url.removeprefix(_LOCAL_SCHEME)}"
    return url
