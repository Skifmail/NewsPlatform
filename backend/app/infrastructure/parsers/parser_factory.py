"""Фабрика парсеров по типу источника."""

from app.domain.enums import SourceType
from app.infrastructure.models.source import Source
from app.infrastructure.parsers.base import BaseParser
from app.infrastructure.parsers.rss_parser import RssParser
from app.infrastructure.parsers.telegram_parser import TelegramParser
from app.infrastructure.parsers.web_parser import WebParser


def get_parser(source: Source) -> BaseParser:
    """Возвращает парсер для типа источника.

    Args:
        source: модель источника.

    Returns:
        BaseParser: реализация парсера.

    Raises:
        ValueError: неизвестный тип.
    """
    parsers: dict[str, BaseParser] = {
        SourceType.RSS.value: RssParser(),
        SourceType.TELEGRAM.value: TelegramParser(),
        SourceType.WEB.value: WebParser(),
    }
    parser = parsers.get(source.type)
    if not parser:
        msg = f"Unknown source type: {source.type}"
        raise ValueError(msg)
    return parser
