"""Настройки длинных Telegram-статей (Github, Параграф).

Revision ID: 017
Revises: 016
Create Date: 2026-06-24
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_SETTINGS: list[tuple[str, str]] = [
    (
        "article_telegram_max_length",
        "3800",
    ),
]


def upgrade() -> None:
    conn = op.get_bind()
    for key, value in NEW_SETTINGS:
        exists = conn.execute(
            sa.text("SELECT 1 FROM settings WHERE key = :key"),
            {"key": key},
        ).fetchone()
        if not exists:
            conn.execute(
                sa.text(
                    "INSERT INTO settings (key, value) VALUES (:key, :value)"
                ),
                {"key": key, "value": value},
            )


def downgrade() -> None:
    conn = op.get_bind()
    for key, _ in NEW_SETTINGS:
        conn.execute(
            sa.text("DELETE FROM settings WHERE key = :key"),
            {"key": key},
        )
