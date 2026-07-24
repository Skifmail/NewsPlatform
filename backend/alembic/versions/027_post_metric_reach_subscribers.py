"""Add reach_subscribers to post_metrics.

Revision ID: 027
Revises: 026
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa

revision = "027"
down_revision = "026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "post_metrics",
        sa.Column("reach_subscribers", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("post_metrics", "reach_subscribers")
