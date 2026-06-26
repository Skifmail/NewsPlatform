"""Дата публикации поста в post_metrics

Revision ID: 014
Revises: 013
Create Date: 2026-06-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "post_metrics",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_post_metrics_published_at",
        "post_metrics",
        ["published_at"],
    )
    op.execute(
        """
        UPDATE post_metrics pm
        SET published_at = pl.published_at
        FROM publish_log pl
        WHERE pm.publish_log_id = pl.id
          AND pm.published_at IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_post_metrics_published_at", table_name="post_metrics")
    op.drop_column("post_metrics", "published_at")
