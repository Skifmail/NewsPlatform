"""Seed ideation prompts for manual topic/occasion override.

Importers: alembic upgrade head (deployment).
Affected API: GET/PATCH/POST /api/prompts surfaces new keys ideation.manual_topic
and ideation.manual_postcard (no route changes, data-only migration).
Data schema: prompt_templates rows — inserts two new keys from PROMPT_DEFAULTS.
User instruction: add editable prompts for manual theme on Channels generate-article.

Revision ID: 032
Revises: 031
Create Date: 2026-07-27
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "032"
down_revision = "031"
branch_labels = None
depends_on = None

_NEW_KEYS = (
    "ideation.manual_topic",
    "ideation.manual_postcard",
)


def upgrade() -> None:
    from app.domain.prompt_defaults import PROMPT_DEFAULTS

    conn = op.get_bind()
    for key in _NEW_KEYS:
        entry = PROMPT_DEFAULTS[key]
        conn.execute(
            sa.text(
                "INSERT INTO prompt_templates "
                "(key, category, name, description, template_text, "
                "template_variables, channel_scope, is_system_prompt, sort_order) "
                "VALUES (:key, :category, :name, :description, :template_text, "
                ":template_variables, :channel_scope, :is_system_prompt, :sort_order) "
                "ON CONFLICT (key) DO NOTHING"
            ),
            {
                "key": entry.key,
                "category": entry.category,
                "name": entry.name,
                "description": entry.description,
                "template_text": entry.template_text,
                "template_variables": json.dumps(entry.template_variables),
                "channel_scope": entry.channel_scope,
                "is_system_prompt": entry.is_system_prompt,
                "sort_order": entry.sort_order,
            },
        )


def downgrade() -> None:
    conn = op.get_bind()
    for key in _NEW_KEYS:
        conn.execute(
            sa.text("DELETE FROM prompt_templates WHERE key = :key"),
            {"key": key},
        )
