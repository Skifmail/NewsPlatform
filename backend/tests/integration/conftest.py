"""Параметры только изолированных интеграционных проверок."""

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Добавляет явный адрес отдельной PostgreSQL для проверок блокировок.

    Args:
        parser: Парсер параметров pytest.
    """
    parser.addoption("--supplement-postgres-url", default=None)
