"""Общие хелперы доступа к Bot API MAX.

Содержит базовый URL и создание ``aiohttp.ClientSession`` с TLS-контекстом,
доверяющим сертификатам Минцифры (Russian Trusted Root/Sub CA), которыми
подписан ``platform-api2.max.ru``. Эти CA отсутствуют в системном хранилище,
поэтому без них запросы падают с ``CERTIFICATE_VERIFY_FAILED``.
"""

from __future__ import annotations

import ssl
from functools import lru_cache
from pathlib import Path

import aiohttp
from loguru import logger

from app.core.config import get_settings

_DEFAULT_CA_BUNDLE = (
    Path(__file__).resolve().parents[1]
    / "infrastructure"
    / "certs"
    / "russian_trusted_ca.pem"
)


def get_max_api_base() -> str:
    """Возвращает базовый URL Bot API MAX без завершающего слэша."""
    return get_settings().max_api_base.rstrip("/")


def _ca_bundle_path() -> Path | None:
    """Возвращает путь к PEM-бандлу CA или None, если файл недоступен."""
    configured = (get_settings().max_ca_bundle or "").strip()
    path = Path(configured) if configured else _DEFAULT_CA_BUNDLE
    if path.is_file():
        return path
    logger.warning(
        "MAX CA bundle not found, falling back to system trust store",
        path=str(path),
    )
    return None


@lru_cache(maxsize=1)
def get_max_ssl_context() -> ssl.SSLContext | None:
    """Строит SSL-контекст с системными CA + бандлом Минцифры.

    Returns:
        ssl.SSLContext | None: контекст с доверенными CA или None, если бандл
        не найден (тогда используется системное хранилище по умолчанию).
    """
    bundle = _ca_bundle_path()
    if bundle is None:
        return None
    context = ssl.create_default_context()
    try:
        context.load_verify_locations(cafile=str(bundle))
    except ssl.SSLError as exc:
        logger.warning(
            "Failed to load MAX CA bundle, using system trust store",
            path=str(bundle),
            error=str(exc),
        )
        return None
    return context


def max_client_session(**kwargs: object) -> aiohttp.ClientSession:
    """Создаёт ``aiohttp.ClientSession`` с доверием к CA Минцифры.

    Args:
        **kwargs: дополнительные параметры ``aiohttp.ClientSession``.

    Returns:
        aiohttp.ClientSession: сессия с настроенным TLS-контекстом.
    """
    context = get_max_ssl_context()
    connector = aiohttp.TCPConnector(ssl=context) if context is not None else None
    return aiohttp.ClientSession(connector=connector, **kwargs)
