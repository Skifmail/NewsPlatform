"""Тесты определения long-form Telegram-каналов."""

from app.infrastructure.models.channel import Channel
from app.utils.telegram_channels import (
    is_long_form_article_channel,
    is_telegram_long_form_channel,
)


def test_github_channel_is_long_form() -> None:
    channel = Channel(
        id=6,
        name="Github | Находки",
        platform="telegram",
        platform_id="-1004461561041",
        topic="it",
        content_mode="article",
    )
    assert is_telegram_long_form_channel(channel)


def test_paragraph_channel_is_long_form() -> None:
    channel = Channel(
        id=5,
        name="ПАРАГРАФ",
        platform="telegram",
        platform_id="-1003959703552",
        topic="it",
        content_mode="article",
    )
    assert is_telegram_long_form_channel(channel)


def test_news_channel_is_not_long_form() -> None:
    channel = Channel(
        id=2,
        name="АВТОСФЕРА | Новости",
        platform="telegram",
        platform_id="-1004244141982",
        topic="auto",
        content_mode="news",
    )
    assert not is_telegram_long_form_channel(channel)


def test_paragraph_max_channel_is_long_form() -> None:
    channel = Channel(
        id=8,
        name="ПАРАГРАФ (МАКС)",
        platform="max",
        platform_id="https://max.ru/paragraph",
        topic="it",
        content_mode="article",
    )
    assert is_long_form_article_channel(channel)


def test_news_max_channel_is_not_long_form() -> None:
    channel = Channel(
        id=9,
        name="Сводка | Новости (МАКС)",
        platform="max",
        platform_id="https://max.ru/svodka",
        topic="russia",
        content_mode="news",
    )
    assert not is_long_form_article_channel(channel)
