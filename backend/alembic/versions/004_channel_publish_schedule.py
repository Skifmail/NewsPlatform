"""Расписание публикации по каналам.

Revision ID: 004
Revises: 003
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Добавляет поля интервала и окна публикации на канал."""
    op.add_column(
        "channels",
        sa.Column(
            "publish_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )
    op.add_column(
        "channels",
        sa.Column(
            "publish_window_start",
            sa.String(5),
            nullable=False,
            server_default="08:00",
        ),
    )
    op.add_column(
        "channels",
        sa.Column(
            "publish_window_end",
            sa.String(5),
            nullable=False,
            server_default="22:00",
        ),
    )


def downgrade() -> None:
    """Удаляет поля расписания."""
    op.drop_column("channels", "publish_window_end")
    op.drop_column("channels", "publish_window_start")
    op.drop_column("channels", "publish_interval_minutes")
