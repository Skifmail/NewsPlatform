"""Убирает из промпта спорта инструкцию «выпиши факты в ответ».

Revision ID: 011
Revises: 010
Create Date: 2026-06-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_BLOCK = """ВАЖНО ПЕРЕД ПЕРЕПИСЫВАНИЕМ:
Сначала выпиши для себя все факты из оригинала: что произошло, какие цифры
(счёт, суммы трансферов, сроки контрактов, сроки дисквалификации), кто
вовлечён (клубы, спортсмены, федерации), есть ли официальная реакция сторон."""

_NEW_BLOCK = """Чек-лист фактов (счёт, сроки, стороны) держи в голове, но в ответе
выдай ТОЛЬКО HTML поста — без черновиков, списков фактов и рассуждений."""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE channels SET style_prompt = REPLACE(style_prompt, :old, :new) "
            "WHERE id = 4 AND style_prompt LIKE :pattern"
        ),
        {
            "old": _OLD_BLOCK,
            "new": _NEW_BLOCK,
            "pattern": "%ВАЖНО ПЕРЕД ПЕРЕПИСЫВАНИЕМ%",
        },
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE channels SET style_prompt = REPLACE(style_prompt, :new, :old) "
            "WHERE id = 4 AND style_prompt LIKE :pattern"
        ),
        {
            "old": _OLD_BLOCK,
            "new": _NEW_BLOCK,
            "pattern": "%Чек-лист фактов%",
        },
    )
