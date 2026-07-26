"""Create prompt_templates table, seed defaults, migrate overrides from settings.

Importers: alembic upgrade head (deployment).
Affected API: creates table for GET/PATCH /api/prompts, POST /api/prompts/{key}/reset.
Data schema: prompt_templates table ← PromptTemplate model; seeds from PROMPT_DEFAULTS.
User instruction: "не нужно ничего захардкоживать" — все промпты в выделенной таблице.

Revision ID: 030
Revises: 029
Create Date: 2026-07-26
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "030"
down_revision = "029"
branch_labels = None
depends_on = None

SETTINGS_KEY_TO_PROMPT_KEY = {
    "classification_prompt": "classification.user",
    "curated_pick_prompt": "topic_selection.curated_pick",
    "article_ideation_prompt": "ideation.default",
    "article_writing_prompt": "writing.default",
}


def upgrade() -> None:
    op.create_table(
        "prompt_templates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("key", sa.String(120), unique=True, nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column(
            "template_variables", sa.Text(), nullable=False, server_default="[]"
        ),
        sa.Column(
            "channel_scope", sa.String(60), nullable=False, server_default="all"
        ),
        sa.Column(
            "is_system_prompt", sa.Boolean(), nullable=False, server_default="false"
        ),
        sa.Column(
            "sort_order", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
    )

    from app.domain.prompt_defaults import PROMPT_DEFAULTS

    conn = op.get_bind()
    for entry in PROMPT_DEFAULTS.values():
        conn.execute(
            sa.text(
                "INSERT INTO prompt_templates "
                "(key, category, name, description, template_text, "
                "template_variables, channel_scope, is_system_prompt, sort_order) "
                "VALUES (:key, :category, :name, :description, :template_text, "
                ":template_variables, :channel_scope, :is_system_prompt, :sort_order)"
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

    for settings_key, prompt_key in SETTINGS_KEY_TO_PROMPT_KEY.items():
        row = conn.execute(
            sa.text("SELECT value FROM settings WHERE key = :k"),
            {"k": settings_key},
        ).fetchone()
        if row is not None:
            override_text = row[0]
            default_text = PROMPT_DEFAULTS[prompt_key].template_text
            if override_text.strip() != default_text.strip():
                conn.execute(
                    sa.text(
                        "UPDATE prompt_templates SET template_text = :txt "
                        "WHERE key = :k"
                    ),
                    {"txt": override_text, "k": prompt_key},
                )

    conn.execute(
        sa.text(
            "DELETE FROM settings WHERE key IN :keys"
        ).bindparams(
            sa.bindparam("keys", expanding=True)
        ),
        {"keys": list(SETTINGS_KEY_TO_PROMPT_KEY.keys())},
    )


def downgrade() -> None:
    conn = op.get_bind()

    for settings_key, prompt_key in SETTINGS_KEY_TO_PROMPT_KEY.items():
        row = conn.execute(
            sa.text(
                "SELECT template_text FROM prompt_templates WHERE key = :k"
            ),
            {"k": prompt_key},
        ).fetchone()
        if row is not None:
            conn.execute(
                sa.text(
                    "INSERT INTO settings (key, value) VALUES (:k, :v) "
                    "ON CONFLICT (key) DO NOTHING"
                ),
                {"k": settings_key, "v": row[0]},
            )

    op.drop_table("prompt_templates")
