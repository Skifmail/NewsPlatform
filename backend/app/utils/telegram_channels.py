"""Определение режимов публикации Telegram-каналов."""

from app.infrastructure.ai.devtools_teaser_formatter import is_devtools_article_channel
from app.infrastructure.ai.paragraph_teaser_formatter import is_paragraph_article_channel
from app.infrastructure.ai.postcard_teaser_formatter import is_postcard_article_channel
from app.infrastructure.models.channel import Channel
from app.domain.enums import ContentMode


def is_long_form_article_channel(channel: Channel) -> bool:
    """Каналы, где статья публикуется целиком одним сообщением без Telegraph.

    Подходит для любой платформы (Telegram, MAX): Github | Находки, ПАРАГРАФ
    и Открытки в режиме ``content_mode=article``. Для MAX это критично —
    Telegraph недоступен без VPN, а MAX-аудитория читает без него. Для
    Открыток дополнительная причина — короткой открытке не нужна ссылка
    «читать далее», это испортит формат.

    Args:
        channel: канал публикации.

    Returns:
        bool: True если нужен длинный пост в одном сообщении.
    """
    if channel.content_mode != ContentMode.ARTICLE.value:
        return False
    return (
        is_devtools_article_channel(channel.topic, channel.name)
        or is_paragraph_article_channel(channel.name)
        or is_postcard_article_channel(channel.name)
    )


def is_telegram_long_form_channel(channel: Channel) -> bool:
    """Telegram-каналы, где статья уходит целиком без Telegraph.

    Args:
        channel: канал публикации.

    Returns:
        bool: True если нужен длинный пост в одном сообщении.
    """
    return is_long_form_article_channel(channel)
