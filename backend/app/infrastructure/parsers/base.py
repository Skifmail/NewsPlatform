"""Базовый интерфейс парсера."""

from abc import ABC, abstractmethod

from app.domain.entities import RawPostDTO
from app.infrastructure.models.source import Source


class BaseParser(ABC):
    """Абстрактный парсер источника."""

    @abstractmethod
    async def fetch_new(self, source: Source) -> list[RawPostDTO]:
        """Загружает новые посты из источника.

        Args:
            source: модель источника.

        Returns:
            list[RawPostDTO]: новые посты.
        """
