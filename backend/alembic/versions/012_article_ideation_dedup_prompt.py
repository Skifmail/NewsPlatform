"""Усиленный промпт идеации тем статей

Revision ID: 012
Revises: 011
Create Date: 2026-06-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_UPDATED_IDEATION_PROMPT = """Ты — редактор познавательного Telegram-канала «{channel_name}».
Ниша канала: {channel_niche}

Недавние темы и заголовки (СТРОГО ЗАПРЕЩЕНО повторять и близкие по смыслу):
{recent_topics}

Правила выбора темы:
- Одна конкретная концепция = одна статья. Нельзя перефразировать недавнюю тему другими словами.
- Если недавно был «эффект плацебо» — запрещены сахарная таблетка, сила внушения, самовнушение и т.п.
- Если недавно было «дежавю» — запрещены ложные воспоминания, déjà vu, «уже здесь были».
- Чередуй области знаний: космос, история, биология, физика, технологии, культура, экономика, язык, археология.
- Не выбирай подряд несколько тем из одной области (психология мозга, оптические иллюзии и т.д.).
- Тема должна быть интересной широкой аудитории, с потенциалом для фактов из интернета.

Придумай ОДНУ свежую познавательную тему для длинной статьи на русском.

Ответь строго JSON одной строкой:
{{"topic": "краткое название темы", "angle": "угол подачи в 1-2 предложения", "search_queries": ["запрос 1", "запрос 2", "запрос 3"]}}"""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE settings SET value = :value WHERE key = 'article_ideation_prompt'"
        ),
        {"value": _UPDATED_IDEATION_PROMPT},
    )


def downgrade() -> None:
    pass
