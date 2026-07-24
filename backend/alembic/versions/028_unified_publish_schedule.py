"""Unify publishing schedule around publish_times.

Removes publish_interval_minutes, publish_window_start, publish_window_end
from channels and scheduled_at from processed_posts. Backfills any empty
publish_times with a sensible default (every 40 min from 07:00 to 23:00 MSK).

Revision ID: 028
Revises: 027
Create Date: 2026-07-24
"""

from alembic import op
import sqlalchemy as sa

revision = "028"
down_revision = "027"
branch_labels = None
depends_on = None


DEFAULT_PUBLISH_TIMES = (
    "07:00,07:40,08:20,09:00,09:40,10:20,11:00,11:40,12:20,13:00,13:40,"
    "14:20,15:00,15:40,16:20,17:00,17:40,18:20,19:00,19:40,20:20,21:00,"
    "21:40,22:20,23:00"
)


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE channels SET publish_times = :times "
            "WHERE publish_times IS NULL OR publish_times = ''"
        ).bindparams(times=DEFAULT_PUBLISH_TIMES)
    )
    op.alter_column(
        "channels",
        "publish_times",
        existing_type=sa.String(length=255),
        nullable=False,
        server_default=DEFAULT_PUBLISH_TIMES,
    )
    op.drop_column("channels", "publish_interval_minutes")
    op.drop_column("channels", "publish_window_start")
    op.drop_column("channels", "publish_window_end")
    op.drop_column("processed_posts", "scheduled_at")


def downgrade() -> None:
    op.add_column(
        "processed_posts",
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "channels",
        sa.Column(
            "publish_window_end",
            sa.String(length=5),
            nullable=False,
            server_default="22:00",
        ),
    )
    op.add_column(
        "channels",
        sa.Column(
            "publish_window_start",
            sa.String(length=5),
            nullable=False,
            server_default="08:00",
        ),
    )
    op.add_column(
        "channels",
        sa.Column(
            "publish_interval_minutes",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )
    op.alter_column(
        "channels",
        "publish_times",
        existing_type=sa.String(length=255),
        nullable=True,
        server_default=None,
    )
