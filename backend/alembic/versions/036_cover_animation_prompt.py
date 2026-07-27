"""Broaden cover animation prompt to all article channels.

Revision ID: 036
Revises: 035
Create Date: 2026-07-27
"""

import json

import sqlalchemy as sa
from alembic import op

from app.domain.prompt_defaults import PROMPT_DEFAULTS

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    entry = PROMPT_DEFAULTS["image.postcard_animation"]
    conn = op.get_bind()
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
    conn = op.get_bind()
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
            "key": "image.postcard_animation",
            "name": "Анимация открытки (Grok Imagine Video)",
            "description": (
                "Инструкция для image-to-video: деликатное движение сцены, текст неподвижен"
            ),
            "template_text": (
                "Деликатно анимируй сцену на открытке «{title}»: естественное движение "
                "объектов (волны, пар от чашки, пламя свечей, облака, птицы на фоне). "
                "Весь текст, надписи и типографика остаются абсолютно неподвижными — "
                "без морфинга букв, без дрейфа текста."
            ),
            "channel_scope": "postcard",
        },
    )
