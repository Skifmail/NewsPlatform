"""Конкретные времена выхода статей по МСК (channels.publish_times)

Revision ID: 022
Revises: 021
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("publish_times", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channels", "publish_times")
