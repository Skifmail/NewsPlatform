"""Add post_text to post_metrics for stats export.

Revision ID: 038
Revises: 037
Create Date: 2026-08-21
"""

import sqlalchemy as sa

from alembic import op

revision = "038"
down_revision = "037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "post_metrics",
        sa.Column("post_text", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("post_metrics", "post_text")
