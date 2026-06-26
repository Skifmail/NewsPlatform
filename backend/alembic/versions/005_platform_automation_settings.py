"""Platform automation settings keys

Revision ID: 005
Revises: 004
Create Date: 2026-06-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_SETTINGS: list[tuple[str, str]] = [
    ("schedule_fetch_enabled", "true"),
    ("schedule_ai_enabled", "true"),
    ("schedule_publish_enabled", "true"),
    ("schedule_retention_enabled", "true"),
    ("manual_fetch_enabled", "true"),
    ("manual_ai_enabled", "true"),
    ("manual_publish_enabled", "true"),
    ("auto_ai_after_manual_fetch", "true"),
    ("fetch_interval_minutes", "30"),
    ("retention_hour_utc", "3"),
    ("retention_minute_utc", "30"),
    ("fetch_max_age_days", "1"),
]

REMOVED_KEYS: list[str] = [key for key, _ in NEW_SETTINGS]


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
    for key in REMOVED_KEYS:
        conn.execute(
            sa.text("DELETE FROM settings WHERE key = :key"),
            {"key": key},
        )
