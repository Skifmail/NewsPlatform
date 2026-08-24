"""Require emojis throughout Paragraph posts, not only in title.

Revision ID: 044
Revises: 043
"""

import sqlalchemy as sa
from alembic import op

from app.domain.prompt_defaults import PROMPT_DEFAULTS

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None

_PROMPT_KEYS = (
    "writing.system_paragraph",
    "writing.paragraph_instructions",
)


def upgrade() -> None:
    conn = op.get_bind()
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
    pass
