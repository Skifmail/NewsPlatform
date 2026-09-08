"""Каталог хэштегов канала + промпты Параграфа с выбором 1–2 тегов.

Revision ID: 045
Revises: 044
"""

import sqlalchemy as sa
from alembic import op

from app.domain.hashtags import PARAGRAPH_HASHTAGS
from app.domain.prompt_defaults import PROMPT_DEFAULTS

revision = "045"
down_revision = "044"
branch_labels = None
depends_on = None

_PROMPT_KEYS = (
    "writing.system_paragraph",
    "writing.paragraph_instructions",
)

_PARAGRAPH_HASHTAGS_VALUE = "\n".join(PARAGRAPH_HASHTAGS)


def upgrade() -> None:
    op.add_column("channels", sa.Column("hashtags", sa.Text(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE channels
            SET hashtags = :tags
            WHERE lower(name) LIKE '%параграф%'
              AND (hashtags IS NULL OR btrim(hashtags) = '')
            """
        ),
        {"tags": _PARAGRAPH_HASHTAGS_VALUE},
    )

    for key in _PROMPT_KEYS:
        entry = PROMPT_DEFAULTS[key]
        conn.execute(
            sa.text(
                """
                UPDATE prompt_templates
                SET name = :name,
                    description = :description,
                    template_text = :template_text,
                    channel_scope = :channel_scope,
                    updated_at = NOW()
                WHERE key = :key
                """
            ),
            {
                "key": entry.key,
                "name": entry.name,
                "description": entry.description,
                "template_text": entry.template_text,
                "channel_scope": entry.channel_scope,
            },
        )


def downgrade() -> None:
    op.drop_column("channels", "hashtags")
