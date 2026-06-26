"""Режим статей: content_mode каналов и поля processed_posts

Revision ID: 009
Revises: 008
Create Date: 2026-06-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_SETTINGS: list[tuple[str, str]] = [
    ("schedule_article_publish_enabled", "false"),
    (
        "article_ideation_prompt",
        """Ты — редактор познавательного Telegram-канала «{channel_name}».
Ниша канала: {channel_niche}

Недавние темы (не повторяй): {recent_topics}

Придумай ОДНУ свежую познавательную тему для длинной статьи на русском.
Тема должна быть интересной широкой аудитории, с потенциалом для фактов из интернета.

Ответь строго JSON одной строкой:
{{"topic": "краткое название темы", "angle": "угол подачи в 1-2 предложения", "search_queries": ["запрос 1", "запрос 2", "запрос 3"]}}""",
    ),
    (
        "article_writing_prompt",
        """Ты — автор познавательных статей для Telegram-канала «{channel_name}».
Стиль канала: {channel_niche}

Напиши статью на русском по теме «{topic}» ({angle}).
Используй ТОЛЬКО факты из блока «Исследование» ниже. Не выдумывай цитаты и цифры.

Структура:
1) Цепляющий заголовок (в поле title, не в body)
2) Лид — 2-3 предложения
3) 3-5 разделов с подзаголовками <b>...</b>
4) Вывод — 2-3 предложения
5) Блок «Источники» — список ссылок <a href="...">название</a>

HTML в body_html: только теги b, i, a, blockquote. Без <p>. Абзацы — пустая строка.
Объём body_html: {min_length}–{max_length} символов.
Teaser (анонс для Telegram): до {teaser_max_length} символов, интригует, без спойлеров всей статьи.

Ответь строго JSON:
{{"title": "...", "teaser": "...", "body_html": "...", "image_prompt": "описание обложки на английском для DALL-E"}}

Исследование:
{research_context}""",
    ),
    ("article_teaser_max_length", "900"),
    ("article_body_max_length", "12000"),
]


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "content_mode",
            sa.String(length=32),
            nullable=False,
            server_default="news",
        ),
    )
    op.alter_column("processed_posts", "raw_post_id", nullable=True)
    op.add_column(
        "processed_posts",
        sa.Column(
            "content_mode",
            sa.String(length=32),
            nullable=False,
            server_default="news",
        ),
    )
    op.add_column(
        "processed_posts",
        sa.Column("article_title", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "processed_posts",
        sa.Column("article_body", sa.Text(), nullable=True),
    )
    op.add_column(
        "processed_posts",
        sa.Column("telegraph_url", sa.Text(), nullable=True),
    )
    op.add_column(
        "processed_posts",
        sa.Column("research_sources", sa.Text(), nullable=True),
    )

    conn = op.get_bind()
    for key, value in NEW_SETTINGS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM settings WHERE key = :key"),
            {"key": key},
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO settings (key, value) VALUES (:key, :value)"
                ),
                {"key": key, "value": value},
            )


def downgrade() -> None:
    conn = op.get_bind()
    for key, _ in NEW_SETTINGS:
        conn.execute(
            sa.text("DELETE FROM settings WHERE key = :key"),
            {"key": key},
        )
    op.drop_column("processed_posts", "research_sources")
    op.drop_column("processed_posts", "telegraph_url")
    op.drop_column("processed_posts", "article_body")
    op.drop_column("processed_posts", "article_title")
    op.drop_column("processed_posts", "content_mode")
    op.alter_column("processed_posts", "raw_post_id", nullable=False)
    op.drop_column("channels", "content_mode")
