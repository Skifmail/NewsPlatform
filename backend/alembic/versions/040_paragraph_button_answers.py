"""Add button_answers JSON for callback option breakdown."""

from alembic import op
import sqlalchemy as sa

revision = "040"
down_revision = "039"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "post_metrics",
        sa.Column("button_answers", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("post_metrics", "button_answers")
