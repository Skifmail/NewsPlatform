"""Таблица участников MAX-каналов (полная аналитика подписчиков)

Revision ID: 020
Revises: 019
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "max_members",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("first_name", sa.String(length=255), nullable=True),
        sa.Column("last_name", sa.String(length=255), nullable=True),
        sa.Column("name", sa.String(length=512), nullable=True),
        sa.Column("username", sa.String(length=255), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("is_bot", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_owner", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("permissions", sa.Text(), nullable=True),
        sa.Column("join_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_access_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_present", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "first_seen_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["channel_id"], ["channels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("channel_id", "user_id", name="uq_max_members_channel_user"),
    )
    op.create_index("ix_max_members_channel_id", "max_members", ["channel_id"])
    op.create_index("ix_max_members_join_at", "max_members", ["join_at"])
    op.create_index("ix_max_members_is_present", "max_members", ["is_present"])


def downgrade() -> None:
    op.drop_index("ix_max_members_is_present", table_name="max_members")
    op.drop_index("ix_max_members_join_at", table_name="max_members")
    op.drop_index("ix_max_members_channel_id", table_name="max_members")
    op.drop_table("max_members")
