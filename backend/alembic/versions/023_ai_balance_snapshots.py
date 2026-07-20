"""История баланса AI-провайдеров (ai_balance_snapshots)

Revision ID: 023
Revises: 022
Create Date: 2026-07-20

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ai_balance_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("total_balance", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("granted_balance", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column("topped_up_balance", sa.Numeric(precision=20, scale=8), nullable=True),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_balance_snapshots_provider", "ai_balance_snapshots", ["provider"]
    )
    op.create_index(
        "ix_ai_balance_snapshots_captured_at", "ai_balance_snapshots", ["captured_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_ai_balance_snapshots_captured_at", table_name="ai_balance_snapshots")
    op.drop_index("ix_ai_balance_snapshots_provider", table_name="ai_balance_snapshots")
    op.drop_table("ai_balance_snapshots")
