"""Add app_error_logs table for in-panel error/diagnostics window.

Revision ID: 029
Revises: 028
Create Date: 2026-07-25
"""

from alembic import op
import sqlalchemy as sa

revision = "029"
down_revision = "028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "app_error_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False, server_default="app"),
        sa.Column("source", sa.String(length=512), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("context", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_app_error_logs_created_at", "app_error_logs", ["created_at"]
    )
    op.create_index("ix_app_error_logs_level", "app_error_logs", ["level"])


def downgrade() -> None:
    op.drop_index("ix_app_error_logs_level", table_name="app_error_logs")
    op.drop_index("ix_app_error_logs_created_at", table_name="app_error_logs")
    op.drop_table("app_error_logs")
