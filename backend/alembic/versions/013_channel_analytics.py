"""Таблицы аналитики каналов и настройки автосбора

Revision ID: 013
Revises: 012
Create Date: 2026-06-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_SETTINGS: list[tuple[str, str]] = [
    ("schedule_analytics_enabled", "false"),
    ("analytics_interval_minutes", "180"),
]


def upgrade() -> None:
    op.create_table(
        "channel_stats_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("subscribers", sa.Integer(), nullable=True),
        sa.Column("posts_count", sa.Integer(), nullable=True),
        sa.Column("total_views", sa.Integer(), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_channel_stats_snapshots_channel_id",
        "channel_stats_snapshots",
        ["channel_id"],
    )
    op.create_index(
        "ix_channel_stats_snapshots_captured_at",
        "channel_stats_snapshots",
        ["captured_at"],
    )

    op.create_table(
        "post_metrics",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("processed_post_id", sa.Integer(), nullable=True),
        sa.Column("publish_log_id", sa.Integer(), nullable=True),
        sa.Column("platform_post_id", sa.String(length=255), nullable=False),
        sa.Column("post_url", sa.String(length=512), nullable=True),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("forwards", sa.Integer(), nullable=True),
        sa.Column("reactions", sa.Integer(), nullable=True),
        sa.Column("comments", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["processed_post_id"], ["processed_posts.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["publish_log_id"], ["publish_log.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "channel_id", "platform_post_id", name="uq_post_metrics_channel_post"
        ),
    )
    op.create_index("ix_post_metrics_channel_id", "post_metrics", ["channel_id"])
    op.create_index("ix_post_metrics_collected_at", "post_metrics", ["collected_at"])

    op.create_table(
        "ad_integrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("processed_post_id", sa.Integer(), nullable=True),
        sa.Column("platform_post_id", sa.String(length=255), nullable=True),
        sa.Column("post_url", sa.String(length=512), nullable=True),
        sa.Column("advertiser", sa.String(length=255), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column(
            "currency", sa.String(length=8), server_default="RUB", nullable=False
        ),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status", sa.String(length=32), server_default="published", nullable=False
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["processed_post_id"], ["processed_posts.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ad_integrations_channel_id", "ad_integrations", ["channel_id"])

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
    op.drop_index("ix_ad_integrations_channel_id", table_name="ad_integrations")
    op.drop_table("ad_integrations")
    op.drop_index("ix_post_metrics_collected_at", table_name="post_metrics")
    op.drop_index("ix_post_metrics_channel_id", table_name="post_metrics")
    op.drop_table("post_metrics")
    op.drop_index(
        "ix_channel_stats_snapshots_captured_at", table_name="channel_stats_snapshots"
    )
    op.drop_index(
        "ix_channel_stats_snapshots_channel_id", table_name="channel_stats_snapshots"
    )
    op.drop_table("channel_stats_snapshots")
