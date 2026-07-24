"""Безопасная подстановка плейсхолдеров без падения на посторонних `{...}`."""


def safe_format(template: str, **kwargs: object) -> str:
    """Заменяет `{key}` на значения kwargs.

    В отличие от `str.format`, не падает, если в шаблоне встречаются
    посторонние фигурные скобки — например, литеральный JSON-пример вида
    `{"topic": "..."}`. Такие фрагменты остаются нетронутыми.

    Args:
        template: шаблон промпта из БД или дефолтного текста.
        **kwargs: подстановки имя→значение.

    Returns:
        str: результат с подставленными плейсхолдерами.
    """
    result = template
    for key, value in kwargs.items():
        result = result.replace("{" + key + "}", str(value))
    return result
