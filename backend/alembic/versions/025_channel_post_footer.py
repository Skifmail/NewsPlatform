"""post_footer — перекрёстные ссылки на другие платформы для канала «Параграф»

Revision ID: 025
Revises: 024
Create Date: 2026-07-23

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Футеры для каждого варианта канала ПАРАГРАФ (ссылки на две другие площадки).
_VK_FOOTER = (
    "—\n"
    "✈️ Telegram: https://t.me/paragraf_article\n"
    "💬 MAX: https://max.ru/se13343929_biz"
)
_TG_FOOTER = (
    "—\n"
    "💙 ВКонтакте: https://vk.ru/paragraf_channel\n"
    "💬 MAX: https://max.ru/se13343929_biz"
)
_MAX_FOOTER = (
    "—\n"
    "💙 ВКонтакте: https://vk.ru/paragraf_channel\n"
    "✈️ Telegram: https://t.me/paragraf_article"
)


def upgrade() -> None:
    op.add_column("channels", sa.Column("post_footer", sa.Text(), nullable=True))

    conn = op.get_bind()
    conn.execute(
        sa.text("UPDATE channels SET post_footer = :f WHERE id = 12"),
        {"f": _VK_FOOTER},
    )
    conn.execute(
        sa.text("UPDATE channels SET post_footer = :f WHERE id = 5"),
        {"f": _TG_FOOTER},
    )
    conn.execute(
        sa.text("UPDATE channels SET post_footer = :f WHERE id = 7"),
        {"f": _MAX_FOOTER},
    )


def downgrade() -> None:
    op.drop_column("channels", "post_footer")
