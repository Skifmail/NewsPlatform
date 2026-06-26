"""Сид начальных RSS-источников."""

import asyncio

from sqlalchemy import select

from app.infrastructure.database import async_session_factory
from app.infrastructure.models.source import Source


SEED_SOURCES = [
    # IT
    {
        "name": "Habr",
        "type": "rss",
        "url": "https://habr.com/ru/rss/all/all/",
        "topic": "it",
    },
    {
        "name": "CNews",
        "type": "rss",
        "url": "https://www.cnews.ru/inc/rss/news.xml",
        "topic": "it",
    },
    {
        "name": "3DNews",
        "type": "rss",
        "url": "https://3dnews.ru/news/rss/",
        "topic": "it",
    },
    # Россия
    {
        "name": "RBC",
        "type": "rss",
        "url": "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
        "topic": "russia",
    },
    {
        "name": "Lenta.ru",
        "type": "rss",
        "url": "https://lenta.ru/rss",
        "topic": "russia",
    },
    {
        "name": "РИА Новости",
        "type": "rss",
        "url": "https://ria.ru/export/rss2/archive/index.xml",
        "topic": "russia",
    },
    # Авто
    {
        "name": "Autostat",
        "type": "rss",
        "url": "https://www.autostat.ru/news/rss/",
        "topic": "auto",
    },
    {
        "name": "Quto",
        "type": "rss",
        "url": "https://quto.ru/exports/rss",
        "topic": "auto",
    },
    {
        "name": "ТАСС Авто",
        "type": "rss",
        "url": "https://tass.ru/rss/v2.xml?section=auto",
        "topic": "auto",
    },
    # Спорт
    {
        "name": "Sports.ru",
        "type": "rss",
        "url": "https://www.sports.ru/rss/all_news.xml",
        "topic": "sport",
    },
    {
        "name": "Коммерсант · Спорт",
        "type": "rss",
        "url": "https://www.kommersant.ru/RSS/section-sport.xml",
        "topic": "sport",
    },
    {
        "name": "Lenta.ru · Спорт",
        "type": "rss",
        "url": "https://lenta.ru/rss/news/sport",
        "topic": "sport",
    },
]


async def seed() -> None:
    """Добавляет источники если их ещё нет.

    Returns:
        None
    """
    async with async_session_factory() as session:
        for item in SEED_SOURCES:
            result = await session.execute(
                select(Source).where(Source.url == item["url"])
            )
            if result.scalar_one_or_none():
                continue
            session.add(Source(**item))
        await session.commit()
    print("Seed completed")


if __name__ == "__main__":
    asyncio.run(seed())
