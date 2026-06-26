"""FK publish_log: разрешить удаление канала.

Revision ID: 018
Revises: 017
Create Date: 2026-06-24
"""

from typing import Sequence, Union

from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "publish_log_channel_id_fkey", "publish_log", type_="foreignkey"
    )
    op.create_foreign_key(
        "publish_log_channel_id_fkey",
        "publish_log",
        "channels",
        ["channel_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint(
        "publish_log_processed_post_id_fkey", "publish_log", type_="foreignkey"
    )
    op.create_foreign_key(
        "publish_log_processed_post_id_fkey",
        "publish_log",
        "processed_posts",
        ["processed_post_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "publish_log_processed_post_id_fkey", "publish_log", type_="foreignkey"
    )
    op.create_foreign_key(
        "publish_log_processed_post_id_fkey",
        "publish_log",
        "processed_posts",
        ["processed_post_id"],
        ["id"],
    )
    op.drop_constraint(
        "publish_log_channel_id_fkey", "publish_log", type_="foreignkey"
    )
    op.create_foreign_key(
        "publish_log_channel_id_fkey",
        "publish_log",
        "channels",
        ["channel_id"],
        ["id"],
    )
