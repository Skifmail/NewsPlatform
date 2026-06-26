"""Промпт-гайдлайны обложек на уровне канала

Revision ID: 010
Revises: 009
Create Date: 2026-06-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_GITHUB_IMAGE_TEMPLATE = (
    'Minimal product-style cover art for developer tool "{tool_name}". '
    "Visual metaphor: {scene}. "
    "One centered 3D icon or physical object, dark charcoal background (#161b22), "
    "soft studio lighting, clean tech blog thumbnail, simple composition, "
    "readable at small size in a Telegram feed. "
    "STRICT: no text, no letters, no numbers, no code, no terminal UI, "
    "no floating windows, no neural network diagrams, no circuit boards, "
    "no cyberpunk, no matrix rain, no busy background."
)

_UPDATED_WRITING_PROMPT = """Ты — автор познавательных статей для Telegram-канала «{channel_name}».
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

Правила обложки (поле image_prompt, только английский):
{image_guidelines}

image_prompt — 1–2 предложения: ОДНА конкретная визуальная метафора инструмента или темы.
Запрещено: нейросети, матричный дождь, голограммы, множество окон, нечитаемый код, любой текст на картинке.

Ответь строго JSON:
{{"title": "...", "teaser": "...", "body_html": "...", "image_prompt": "..."}}

Исследование:
{research_context}"""


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("image_prompt_guidelines", sa.Text(), nullable=True),
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE channels SET image_prompt_guidelines = :tpl "
            "WHERE content_mode = 'article' AND topic = 'it' "
            "AND (name ILIKE '%github%' OR name ILIKE '%находк%')"
        ),
        {"tpl": _GITHUB_IMAGE_TEMPLATE},
    )
    conn.execute(
        sa.text(
            "UPDATE settings SET value = :value WHERE key = 'article_writing_prompt'"
        ),
        {"value": _UPDATED_WRITING_PROMPT},
    )


def downgrade() -> None:
    op.drop_column("channels", "image_prompt_guidelines")
