"""Форматирование короткой открытки-поздравления для канала «Открытки»."""


def is_postcard_article_channel(channel_name: str, topic: str = "") -> bool:
    """Определяет, нужен ли формат короткой открытки.

    Args:
        channel_name: название канала.
        topic: тематика канала (например «postcard»).

    Returns:
        bool: True для канала «Открытки».
    """
    return topic == "postcard" or "открытк" in (channel_name or "").lower()

# Промпт открытки полностью живёт в БД (prompt_templates: writing.postcard) —
# отдельных «инструкций-аппендов» для открыток нет, шаблон статьи заменяется целиком.
