"""Настройка структурированного логирования loguru."""

import sys
from pathlib import Path

from loguru import logger

from app.core.config import get_settings

LOG_DIR = Path("logs")


def setup_logging() -> None:
    """Инициализирует loguru: консоль и ротация файлов по уровням.

    Returns:
        None
    """
    settings = get_settings()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    for level in ("DEBUG", "INFO", "WARNING", "ERROR"):
        logger.add(
            LOG_DIR / f"app_{level.lower()}.log",
            level=level,
            filter=lambda record, lvl=level: record["level"].name == lvl,
            rotation="10 MB",
            retention="14 days",
            encoding="utf-8",
        )
