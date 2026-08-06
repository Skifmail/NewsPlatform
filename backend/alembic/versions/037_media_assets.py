"""Add media_assets table for generated image library.

Revision ID: 037
Revises: 036
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa


revision = "037"
down_revision = "036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("channel_id", sa.Integer(), nullable=False),
        sa.Column("processed_post_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="cover"),
        sa.Column("image_source", sa.String(length=50), nullable=True),
        sa.Column("storage_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["channel_id"],
            ["channels.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["processed_post_id"],
            ["processed_posts.id"],
            ondelete="SET NULL",
        ),
        sa.UniqueConstraint("storage_url", name="uq_media_assets_storage_url"),
    )
    op.create_index("ix_media_assets_channel_id", "media_assets", ["channel_id"])
    op.create_index(
        "ix_media_assets_processed_post_id", "media_assets", ["processed_post_id"]
    )
    op.create_index("ix_media_assets_created_at", "media_assets", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_media_assets_created_at", table_name="media_assets")
    op.drop_index("ix_media_assets_processed_post_id", table_name="media_assets")
    op.drop_index("ix_media_assets_channel_id", table_name="media_assets")
    op.drop_table("media_assets")
