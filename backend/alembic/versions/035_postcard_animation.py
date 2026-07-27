"""Add postcard animation: channel flag, video URL on posts, animation prompt.

Revision ID: 035
Revises: 034
Create Date: 2026-07-27
"""

import sqlalchemy as sa
from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


import json

from app.domain.prompt_defaults import PROMPT_DEFAULTS


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column(
            "animate_postcards",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    entry = PROMPT_DEFAULTS["image.postcard_animation"]
    op.execute(
        sa.text(
            """
            INSERT INTO prompt_templates (
                key, category, name, description, template_text,
                template_variables, channel_scope, is_system_prompt, sort_order
            ) VALUES (
                :key, :category, :name, :description, :template_text,
                :template_variables, :channel_scope, false, :sort_order
            )
            ON CONFLICT (key) DO UPDATE SET
                name = EXCLUDED.name,
                description = EXCLUDED.description,
                template_text = EXCLUDED.template_text,
                template_variables = EXCLUDED.template_variables,
                channel_scope = EXCLUDED.channel_scope,
                sort_order = EXCLUDED.sort_order,
                updated_at = NOW()
            """
        ),
        {
            "key": entry.key,
            "category": entry.category,
            "name": entry.name,
            "description": entry.description,
            "template_text": entry.template_text,
            "template_variables": json.dumps(entry.template_variables),
            "channel_scope": entry.channel_scope,
            "sort_order": entry.sort_order,
        },
    )

    op.add_column(
        "processed_posts",
        sa.Column("generated_video_url", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("processed_posts", "generated_video_url")
    op.drop_column("channels", "animate_postcards")

# Prompt seed appended via patch - see upgrade() below
