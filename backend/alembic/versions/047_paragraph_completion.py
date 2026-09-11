"""Завершённые истории ПАРАГРАФА вместо коротких анонсов.

Revision ID: 047
Revises: 046

Пользовательские правила хэштегов сохраняются. Перед применением на production
нужно сохранить три обновляемые записи prompt_templates для ручного отката.
"""

import json
from typing import Final

import sqlalchemy as sa

from alembic import op
from app.domain.prompt_defaults import PROMPT_DEFAULTS

revision: str = "047"
down_revision: str = "046"
branch_labels: None = None
depends_on: None = None

_PROMPT_KEYS: Final[tuple[str, ...]] = (
    "writing.system_paragraph",
    "writing.paragraph_instructions",
    "ideation.system_paragraph",
)
_HASHTAG_START: Final[str] = "- hashtags"
_HASHTAG_END: Final[str] = "- title"


def upgrade() -> None:
    """Обновляет авторское задание и поиск последствий без смены правил тегов."""
    connection = op.get_bind()
    for key in _PROMPT_KEYS:
        current = connection.execute(
            sa.text("SELECT template_text FROM prompt_templates WHERE key = :key"),
            {"key": key},
        ).scalar_one_or_none()
        if current is None:
            continue
        entry = PROMPT_DEFAULTS[key]
        template = entry.template_text
        if key == "writing.paragraph_instructions":
            start = current.find(_HASHTAG_START)
            end = current.find(_HASHTAG_END, start)
            if start >= 0 and end > start:
                new_start = template.index(_HASHTAG_START)
                new_end = template.index(_HASHTAG_END, new_start)
                template = (
                    template[:new_start] + current[start:end] + template[new_end:]
                )
        connection.execute(
            sa.text(
                "UPDATE prompt_templates SET template_text = :template, "
                "template_variables = :variables, updated_at = CURRENT_TIMESTAMP "
                "WHERE key = :key"
            ),
            {
                "key": key,
                "template": template,
                "variables": json.dumps(entry.template_variables),
            },
        )


def downgrade() -> None:
    """Сохраняет редакционный текст; прежние настройки восстанавливаются из бэкапа."""
