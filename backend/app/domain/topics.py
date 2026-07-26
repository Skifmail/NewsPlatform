"""Тематики контента платформы."""

TOPIC_PATTERN = r"^(it|auto|russia|sport|postcard)$"

TOPIC_LABELS: dict[str, str] = {
    "it": "IT",
    "auto": "Авто",
    "russia": "Россия",
    "sport": "Спорт",
    "postcard": "Открытки",
}

# Промпты классификации живут в БД (prompt_templates: classification.*),
# дефолты — в app/domain/prompt_defaults.py.
