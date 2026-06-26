"""Индексы для списков и очереди.

Revision ID: 003
Revises: 002
Create Date: 2026-06-04

"""

from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_processed_posts_status",
        "processed_posts",
        ["status"],
        unique=False,
    )
    op.execute(
        """
        CREATE INDEX ix_raw_posts_source_processed_fetched
        ON raw_posts (source_id, is_processed, fetched_at DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_raw_posts_source_processed_fetched")
    op.drop_index("ix_processed_posts_status", table_name="processed_posts")
