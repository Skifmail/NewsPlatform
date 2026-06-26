"""Тематика sport и обновление промпта классификации

Revision ID: 008
Revises: 007
Create Date: 2026-06-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UPDATED_CLASSIFICATION_PROMPT = """Определи тематику новости. Ответь ТОЛЬКО одним словом: it, auto, russia или sport.
- it: технологии, программирование, гаджеты, интернет, AI
- auto: автомобили, мотоциклы, ПДД, дороги, транспорт
- russia: политика, экономика, общество, события в России
- sport: спорт, соревнования, трансферы, матчи, олимпиада

Новость: {text}"""


def upgrade() -> None:
    """Добавляет sport в промпт классификации для существующих инсталляций."""
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT value FROM settings WHERE key = 'classification_prompt'")
    ).fetchone()
    if row is None:
        return
    current = row[0] or ""
    if "sport" in current.lower():
        return
    conn.execute(
        sa.text(
            "UPDATE settings SET value = :value WHERE key = 'classification_prompt'"
        ),
        {"value": UPDATED_CLASSIFICATION_PROMPT},
    )


def downgrade() -> None:
    """Откат не восстанавливает старый промпт — правка вручную при необходимости."""
    pass
