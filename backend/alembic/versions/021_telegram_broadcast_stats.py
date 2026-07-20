"""Нативная статистика Telegram-каналов (stats.getBroadcastStats)

Revision ID: 021
Revises: 020
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "telegram_broadcast_stats",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("followers", sa.Integer(), nullable=True),
        sa.Column("followers_prev", sa.Integer(), nullable=True),
        sa.Column("views_per_post", sa.Float(), nullable=True),
        sa.Column("views_per_post_prev", sa.Float(), nullable=True),
        sa.Column("shares_per_post", sa.Float(), nullable=True),
        sa.Column("shares_per_post_prev", sa.Float(), nullable=True),
        sa.Column("reactions_per_post", sa.Float(), nullable=True),
        sa.Column("reactions_per_post_prev", sa.Float(), nullable=True),
        sa.Column("enabled_notifications_pct", sa.Float(), nullable=True),
        sa.Column("period_min", sa.DateTime(timezone=True), nullable=True),
        sa.Column("period_max", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telegram_broadcast_stats_channel_id",
        "telegram_broadcast_stats",
        ["channel_id"],
    )
    op.create_index(
        "ix_telegram_broadcast_stats_collected_at",
        "telegram_broadcast_stats",
        ["collected_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_telegram_broadcast_stats_collected_at",
        table_name="telegram_broadcast_stats",
    )
    op.drop_index(
        "ix_telegram_broadcast_stats_channel_id",
        table_name="telegram_broadcast_stats",
    )
    op.drop_table("telegram_broadcast_stats")
