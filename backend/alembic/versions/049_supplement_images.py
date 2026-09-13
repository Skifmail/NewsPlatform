"""Обложки дополнительных публикаций.

Revision ID: 049
Revises: 048
"""

from typing import Final

import sqlalchemy as sa

from alembic import op

revision: str = "049"
down_revision: str = "048"
branch_labels: None = None
depends_on: None = None

_OLD_FACT_RULES: Final = (
    "Один самостоятельный факт, одно предложение, ориентир 20–35 слов."
)
_NEW_FACT_RULES: Final = (
    "Один самостоятельный факт, одно предложение из 12–22 слов. "
    "Одна мысль простыми словами для читателя без специальных знаний."
)
_OLD_NEWS_RULES: Final = (
    "2–3 коротких предложения: что произошло, почему интересно, ограничения. "
    "Отличать гипотезу от результата, лабораторный опыт от готовой технологии."
)
_NEW_NEWS_RULES: Final = (
    "2–3 коротких предложения, каждое до 24 слов: что произошло, почему интересно, "
    "ограничения. Объяснять простыми словами для читателя без специальных знаний. "
    "Отличать гипотезу от результата, лабораторный опыт от готовой технологии."
)


def upgrade() -> None:
    """Добавляет сохранённую версию обязательной обложки."""
    op.add_column("supplement_drafts", sa.Column("image_url", sa.Text(), nullable=True))
    op.add_column(
        "supplement_drafts", sa.Column("image_source", sa.String(50), nullable=True)
    )
    op.add_column(
        "supplement_drafts", sa.Column("image_prompt", sa.Text(), nullable=True)
    )
    configs = sa.table(
        "supplement_configs",
        sa.column("fact_rules", sa.Text()),
        sa.column("news_rules", sa.Text()),
    )
    op.execute(
        configs.update()
        .where(configs.c.fact_rules == _OLD_FACT_RULES)
        .values(fact_rules=_NEW_FACT_RULES)
    )
    op.execute(
        configs.update()
        .where(configs.c.news_rules == _OLD_NEWS_RULES)
        .values(news_rules=_NEW_NEWS_RULES)
    )


def downgrade() -> None:
    """Удаляет только поля обложки дополнительных публикаций."""
    configs = sa.table(
        "supplement_configs",
        sa.column("fact_rules", sa.Text()),
        sa.column("news_rules", sa.Text()),
    )
    op.execute(
        configs.update()
        .where(configs.c.fact_rules == _NEW_FACT_RULES)
        .values(fact_rules=_OLD_FACT_RULES)
    )
    op.execute(
        configs.update()
        .where(configs.c.news_rules == _NEW_NEWS_RULES)
        .values(news_rules=_OLD_NEWS_RULES)
    )
    op.drop_column("supplement_drafts", "image_prompt")
    op.drop_column("supplement_drafts", "image_source")
    op.drop_column("supplement_drafts", "image_url")
