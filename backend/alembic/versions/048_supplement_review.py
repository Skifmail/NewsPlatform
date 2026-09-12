"""Дополнительные публикации с обязательным согласованием MAX.

Revision ID: 048
Revises: 047
"""

import sqlalchemy as sa

from alembic import op

revision: str = "048"
down_revision: str = "047"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    """Создаёт изолированные настройки и черновики, не включая рассылку."""
    op.create_table(
        "supplement_configs",
        sa.Column(
            "channel_id",
            sa.Integer(),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("clock", sa.String(5), nullable=False),
        sa.Column("fact_days", sa.JSON(), nullable=False),
        sa.Column("news_day", sa.Integer(), nullable=False),
        sa.Column("rules", sa.Text(), nullable=False),
        sa.Column("fact_rules", sa.Text(), nullable=False),
        sa.Column("news_rules", sa.Text(), nullable=False),
        sa.Column("recipient_id", sa.BigInteger(), nullable=True),
        sa.Column("recipient_name", sa.String(255), nullable=True),
        sa.Column("pair_hash", sa.String(64), nullable=True, unique=True),
        sa.Column("pair_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "supplement_drafts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "channel_id",
            sa.Integer(),
            sa.ForeignKey("channels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slot_key", sa.String(80), nullable=False),
        sa.Column("requested_kind", sa.String(10), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("trace", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("review_mid", sa.String(255), nullable=True),
        sa.Column("target_chat_id", sa.String(255), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("decided_by", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("platform_mid", sa.String(255), nullable=True),
        sa.Column("platform_url", sa.Text(), nullable=True),
        sa.Column(
            "processed_post_id",
            sa.Integer(),
            sa.ForeignKey("processed_posts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("channel_id", "slot_key", name="uq_supplement_slot"),
    )
    op.create_index(
        "ix_supplement_drafts_channel_id", "supplement_drafts", ["channel_id"]
    )
    op.create_index("ix_supplement_drafts_status", "supplement_drafts", ["status"])


def downgrade() -> None:
    """Удаляет только новые таблицы; опубликованные посты остаются в истории."""
    op.drop_table("supplement_drafts")
    op.drop_table("supplement_configs")
