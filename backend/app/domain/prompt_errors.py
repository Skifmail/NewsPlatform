"""Ошибки системы промпт-шаблонов."""


class PromptNotFoundError(Exception):
    """Промпт не найден в БД."""

    def __init__(self, key: str) -> None:
        self.key = key
        super().__init__(
            f"Промпт '{key}' не найден в БД. "
            f"Проверьте таблицу prompt_templates или запустите миграцию."
        )
