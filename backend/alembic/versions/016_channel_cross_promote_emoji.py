"""ID кастомного эмодзи в ссылке перелива

Revision ID: 016
Revises: 015
Create Date: 2026-06-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("cross_promote_emoji_id", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("channels", "cross_promote_emoji_id")
