"""Чистые правила расписания и обязательного согласования коротких публикаций."""

import re
from datetime import datetime
from typing import Final
from zoneinfo import ZoneInfo

MOSCOW: Final = ZoneInfo("Europe/Moscow")
FACT_LIMIT: Final = 500
NEWS_LIMIT: Final = 1000
PLAIN_SENTENCE_WORD_LIMIT: Final = 24
PLAIN_SENTENCE_COMMA_LIMIT: Final = 1
NEWS_MAX_AGE_DAYS: Final = 7
HISTORY_LIMIT: Final = 80
PAIR_TTL_MINUTES: Final = 15
STALE_MINUTES: Final = 30
DEFAULT_RULES: Final = (
    "Наука, природа, бытовая физика, инженерия и технологии. "
    "Понятное неожиданное открытие без кликбейта и повторов. "
    "Не давать медицинских советов и инструкций опасных опытов. "
    "Предпочитать первоисточники: исследования, университеты, научные организации. "
    "Читатель должен закончить с чувством, а не с вопросом «и что?»."
)
FACT_RULES: Final = (
    "Один самостоятельный факт, одно предложение из 12–22 слов. "
    "Одна ясная картина простыми словами. "
    "Предложение оставляет удивление или ощущение масштаба, а не вопрос «и что?»."
)
NEWS_RULES: Final = (
    "2–3 коротких предложения, каждое до 24 слов. "
    "Сначала конкретная картина простыми словами, затем почему она задевает. "
    "Финал оставляет чувство: удивление, масштаб или странность. "
    "Не заканчивать журналом, датой выхода и оговоркой, после которой читатель "
    "спрашивает «и что?». Лабораторный опыт виден из самой картины, без отдельной "
    "справки «это только модель»."
)


class SupplementError(ValueError):
    """Ошибка правил дополнительной публикации.

    Attributes:
        args: Безопасное для интерфейса описание проблемы.
    """


class DeliveryUncertain(SupplementError):
    """Неопределённый результат внешней отправки, запрещающий слепой повтор.

    Attributes:
        args: Описание необходимости ручной проверки.
    """


def due_kind(
    now: datetime, clock: str, fact_days: list[int], news_day: int
) -> str | None:
    """Выбирает формат наступившего сегодня московского слота.

    Args:
        now: Время с часовым поясом.
        clock: Время HH:MM.
        fact_days: Два разных дня фактов, понедельник равен нулю.
        news_day: День новости, не совпадающий с фактами.

    Returns:
        Формат или None; прошедшие дни не догоняются.

    Raises:
        SupplementError: Время или дни некорректны.
    """
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock):
        raise SupplementError("Укажите время в формате ЧЧ:ММ")
    if (
        len(fact_days) != 2
        or len(set(fact_days + [news_day])) != 3
        or any(
            type(day) is not int or not 0 <= day <= 6 for day in fact_days + [news_day]
        )
    ):
        raise SupplementError("Выберите два дня фактов и отдельный день новости")
    if now.tzinfo is None:
        raise SupplementError("Время должно содержать часовой пояс")
    local = now.astimezone(MOSCOW)
    if local.strftime("%H:%M") < clock:
        return None
    if local.weekday() in fact_days:
        return "fact"
    return "news" if local.weekday() == news_day else None


def validate_text(text: str, kind: str) -> None:
    """Проверяет длину, структуру и понятность текста.

    Args:
        text: Текст без служебных подписей и источников.
        kind: fact или news.

    Raises:
        SupplementError: Текст не соответствует формату.
    """
    if kind not in {"fact", "news"}:
        raise SupplementError("Неизвестный формат")
    limit = FACT_LIMIT if kind == "fact" else NEWS_LIMIT
    if not text.strip() or len(text) > limit or re.search(r"<[^>]*>", text):
        raise SupplementError(f"Нужен обычный текст без HTML, до {limit} символов")
    sentences = [
        part for part in re.split(r"[.!?…]+(?:\s+|$)", text.strip()) if part.strip()
    ]
    if kind == "fact" and len(sentences) != 1:
        raise SupplementError("Факт должен состоять из одного предложения")
    if kind == "news" and not 2 <= len(sentences) <= 3:
        raise SupplementError("Новость должна состоять из двух–трёх предложений")
    for sentence in sentences:
        words = re.findall(r"[A-Za-zА-Яа-яЁё0-9]+(?:-[A-Za-zА-Яа-яЁё0-9]+)*", sentence)
        if (
            len(words) > PLAIN_SENTENCE_WORD_LIMIT
            or sentence.count(",") > PLAIN_SENTENCE_COMMA_LIMIT
        ):
            raise SupplementError(
                "Перепишите материал простыми словами: одна мысль в коротком "
                "предложении без цепочки уточнений"
            )


def validate_decision(
    state: str,
    user_id: int,
    recipient_id: int | None,
    revision: int,
    current_revision: int,
    message_id: str,
    review_mid: str | None,
) -> None:
    """Проверяет право одобрить именно показанную версию.

    Args:
        state: Сохранённый статус.
        user_id: Автор нажатия из заверенного события MAX.
        recipient_id: Привязанный редактор.
        revision: Версия кнопки.
        current_revision: Версия текста в БД.
        message_id: Сообщение с нажатой кнопкой.
        review_mid: Отправленная карточка согласования.

    Raises:
        SupplementError: Карточка чужая, устарела или уже обработана.
    """
    if recipient_id is None or user_id != recipient_id:
        raise SupplementError("Одобрение доступно только привязанному редактору")
    if state != "awaiting" or revision != current_revision:
        raise SupplementError("Карточка уже обработана или устарела")
    if not message_id or message_id != review_mid:
        raise SupplementError("Неверная карточка согласования")
