"""Наблюдаемый прогресс подготовки дополнительных материалов.

Revision ID: 050
Revises: 049
"""

import sqlalchemy as sa

from alembic import op

revision: str = "050"
down_revision: str = "049"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    """Добавляет текущий этап, процент и время обновления процесса."""
    op.add_column(
        "supplement_drafts",
        sa.Column(
            "progress_stage",
            sa.String(40),
            nullable=False,
            server_default="queued",
        ),
    )
    op.add_column(
        "supplement_drafts",
        sa.Column("progress_percent", sa.Integer(), nullable=False, server_default="5"),
    )
    op.add_column(
        "supplement_drafts",
        sa.Column(
            "progress_detail",
            sa.String(255),
            nullable=False,
            server_default="Задание ожидает запуска",
        ),
    )
    op.add_column(
        "supplement_drafts",
        sa.Column(
            "progress_updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    """Удаляет поля наблюдаемого прогресса подготовки."""
    op.drop_column("supplement_drafts", "progress_updated_at")
    op.drop_column("supplement_drafts", "progress_detail")
    op.drop_column("supplement_drafts", "progress_percent")
    op.drop_column("supplement_drafts", "progress_stage")
