"""Финал короткой публикации оставляет чувство, а не оговорку.

Revision ID: 051
Revises: 050
"""

from typing import Final

import sqlalchemy as sa

from alembic import op

revision: str = "051"
down_revision: str = "050"
branch_labels: None = None
depends_on: None = None

_OLD_RULES: Final = (
    "Наука, природа, бытовая физика, инженерия и технологии. "
    "Понятное неожиданное открытие без кликбейта и повторов. "
    "Не давать медицинских советов и инструкций опасных опытов. "
    "Предпочитать первоисточники: исследования, университеты, научные организации."
)
_NEW_RULES: Final = (
    "Наука, природа, бытовая физика, инженерия и технологии. "
    "Понятное неожиданное открытие без кликбейта и повторов. "
    "Не давать медицинских советов и инструкций опасных опытов. "
    "Предпочитать первоисточники: исследования, университеты, научные организации. "
    "Читатель должен закончить с чувством, а не с вопросом «и что?»."
)
_OLD_FACT_RULES: Final = (
    "Один самостоятельный факт, одно предложение из 12–22 слов. "
    "Одна мысль простыми словами для читателя без специальных знаний."
)
_NEW_FACT_RULES: Final = (
    "Один самостоятельный факт, одно предложение из 12–22 слов. "
    "Одна ясная картина простыми словами. "
    "Предложение оставляет удивление или ощущение масштаба, а не вопрос «и что?»."
)
_OLD_NEWS_RULES: Final = (
    "2–3 коротких предложения, каждое до 24 слов: что произошло, почему интересно, "
    "ограничения. Объяснять простыми словами для читателя без специальных знаний. "
    "Отличать гипотезу от результата, лабораторный опыт от готовой технологии."
)
_NEW_NEWS_RULES: Final = (
    "2–3 коротких предложения, каждое до 24 слов. "
    "Сначала конкретная картина простыми словами, затем почему она задевает. "
    "Финал оставляет чувство: удивление, масштаб или странность. "
    "Не заканчивать журналом, датой выхода и оговоркой, после которой читатель "
    "спрашивает «и что?». Лабораторный опыт виден из самой картины, без отдельной "
    "справки «это только модель»."
)


def upgrade() -> None:
    """Заменяет прежние правила, которые требовали финальную оговорку."""
    configs = sa.table(
        "supplement_configs",
        sa.column("rules", sa.Text()),
        sa.column("fact_rules", sa.Text()),
        sa.column("news_rules", sa.Text()),
    )
    op.execute(
        configs.update().where(configs.c.rules == _OLD_RULES).values(rules=_NEW_RULES)
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
    """Возвращает прежние правила коротких публикаций."""
    configs = sa.table(
        "supplement_configs",
        sa.column("rules", sa.Text()),
        sa.column("fact_rules", sa.Text()),
        sa.column("news_rules", sa.Text()),
    )
    op.execute(
        configs.update().where(configs.c.rules == _NEW_RULES).values(rules=_OLD_RULES)
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
