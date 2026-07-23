"""image_prompt_guidelines для канала «Параграф»

Revision ID: 024
Revises: 023
Create Date: 2026-07-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Шаблон обложки для образовательного канала «Параграф».
# {scene} — обработанный image_prompt от ArticleWriter (3–4 предложения с деталями темы).
_PARAGRAPH_IMAGE_TEMPLATE = (
    "Detailed educational scientific illustration: {scene} "
    "Style: photorealistic render or high-quality 3D visualization with rich textures "
    "and accurate real-world detail. "
    "Informative multi-element composition that visually conveys the scientific concept. "
    "Professional soft lighting, clean background. "
    "No text, no letters, no numbers, no people, no faces, "
    "no UI elements, no watermarks."
)


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE channels SET image_prompt_guidelines = :tpl "
            "WHERE content_mode = 'article' AND name ILIKE '%параграф%'"
        ),
        {"tpl": _PARAGRAPH_IMAGE_TEMPLATE},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE channels SET image_prompt_guidelines = NULL "
            "WHERE content_mode = 'article' AND name ILIKE '%параграф%'"
        ),
    )
