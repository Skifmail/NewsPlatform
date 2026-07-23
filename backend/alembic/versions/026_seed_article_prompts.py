"""Засев дефолтных значений article_ideation_prompt и article_writing_prompt

Ключи article_ideation_prompt и article_writing_prompt никогда не попадали в
PLATFORM_SETTINGS_DEFAULTS, поэтому UI показывал пустые поля, хотя рантайм
использовал захардкоженные константы `_DEFAULT_IDEATION_PROMPT` (topic_ideation.py)
и `_DEFAULT_WRITING_PROMPT` (article_writer.py). Копируем их в БД дословно,
чтобы UI отображал реальный шаблон и его можно было править из панели.

INSERT ... ON CONFLICT DO NOTHING — не затираем уже настроенные вручную значения.

Revision ID: 026
Revises: 025
Create Date: 2026-07-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Копия _DEFAULT_IDEATION_PROMPT из app/infrastructure/ai/topic_ideation.py на момент миграции.
_IDEATION_PROMPT = """Ты — редактор познавательного Telegram-канала «{channel_name}».
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


# Копия _DEFAULT_WRITING_PROMPT из app/infrastructure/ai/article_writer.py на момент миграции.
_WRITING_PROMPT = """Ты — автор познавательных статей для Telegram-канала «{channel_name}».
Стиль канала: {channel_niche}

Напиши статью на русском по теме «{topic}» ({angle}).
Используй ТОЛЬКО факты из блока «Исследование» ниже. Не выдумывай цитаты и цифры.

Структура body_html (без служебных меток «Крючок», «Вывод», «Лид», «Источники» — только содержательные подзаголовки):
1) Лид — 2-3 предложения (без заголовка «Лид»)
2) 3-5 разделов с подзаголовками <b>...</b> по теме
3) Заключительный абзац — 2-3 предложения (без заголовка «Вывод»)
4) Ссылки на источники — список <a href="...">название</a> (без заголовка «Источники»)

HTML в body_html: только теги b, i, a, blockquote. Без <p>. Абзацы — через \\n\\n внутри строки JSON.
Объём body_html: {min_length}–{max_length} символов.
Teaser (анонс для Telegram): до {teaser_max_length} символов, интригует, без спойлеров всей статьи.

Правила обложки (поле image_prompt, только английский):
{image_guidelines}

image_prompt — 1–2 предложения: ОДНА конкретная визуальная метафора инструмента или темы.
Запрещено: нейросети, матричный дождь, голограммы, множество окон, нечитаемый код, любой текст на картинке.

Ответь строго одним JSON-объектом с ключами title, teaser, body_html, image_prompt.

Исследование:
{research_context}"""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO settings (key, value) VALUES "
            "('article_ideation_prompt', :ideation), "
            "('article_writing_prompt', :writing) "
            "ON CONFLICT (key) DO NOTHING"
        ),
        {"ideation": _IDEATION_PROMPT, "writing": _WRITING_PROMPT},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM settings WHERE key IN "
            "('article_ideation_prompt', 'article_writing_prompt')"
        )
    )
