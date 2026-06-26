"""Ссылка на другую площадку в конце поста

Revision ID: 015
Revises: 014
Create Date: 2026-06-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("cross_promote_url", sa.String(512), nullable=True),
    )
    op.add_column(
        "channels",
        sa.Column("cross_promote_label", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channels", "cross_promote_label")
    op.drop_column("channels", "cross_promote_url")
