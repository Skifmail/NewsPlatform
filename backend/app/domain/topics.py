"""Тематики контента платформы."""

TOPIC_PATTERN = r"^(it|auto|russia|sport)$"

TOPIC_LABELS: dict[str, str] = {
    "it": "IT",
    "auto": "Авто",
    "russia": "Россия",
    "sport": "Спорт",
}

DEFAULT_CLASSIFICATION_PROMPT = """Определи тематику новости. Ответь ТОЛЬКО одним словом: it, auto, russia или sport.
- it: технологии, программирование, гаджеты, интернет, AI
- auto: автомобили, мотоциклы, ПДД, дороги, транспорт
- russia: политика, экономика, общество, события в России
- sport: спорт, соревнования, трансферы, матчи, олимпиада

Новость: {text}"""

CLASSIFIER_SYSTEM_PROMPT = (
    "Ты классификатор новостей. "
    "Ответь одним словом: it, auto, russia или sport."
)
