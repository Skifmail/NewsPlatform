"""Editorial topic queue, article meta, post metric age buckets.

Revision ID: 039
Revises: 038
Create Date: 2026-08-21

Callers: Channel model/API/UI, ArticleGenerationService, PostMetricsRepository,
ChannelAnalyticsService. Schemas: channels.topic_queue, processed_posts.article_meta,
post_metrics views_*h / button_clicks. User: implement expert recs for Параграф MAX.
"""

import sqlalchemy as sa
from alembic import op

from app.domain.prompt_defaults import PROMPT_DEFAULTS

revision = "039"
down_revision = "038"
branch_labels = None
depends_on = None

_PROMPT_KEYS = (
    "ideation.system_paragraph",
    "ideation.paragraph_extra",
    "writing.system_paragraph",
    "writing.paragraph_instructions",
    "image.writer_hint_paragraph",
    "image.cover_prompt",
)


def upgrade() -> None:
    op.add_column(
        "channels",
        sa.Column("topic_queue", sa.Text(), nullable=True),
    )
    op.add_column(
        "processed_posts",
        sa.Column("article_meta", sa.Text(), nullable=True),
    )
    for col in (
        "views_1h",
        "views_3h",
        "views_24h",
        "views_48h",
        "views_72h",
        "views_7d",
        "subscribers_at_publication",
        "button_clicks",
    ):
        op.add_column("post_metrics", sa.Column(col, sa.Integer(), nullable=True))

    conn = op.get_bind()
    for key in _PROMPT_KEYS:
        entry = PROMPT_DEFAULTS[key]
        conn.execute(
            sa.text(
                """
                UPDATE prompt_templates
                SET name = :name,
                    description = :description,
                    template_text = :template_text,
                    channel_scope = :channel_scope,
                    updated_at = NOW()
                WHERE key = :key
                """
            ),
            {
                "key": entry.key,
                "name": entry.name,
                "description": entry.description,
                "template_text": entry.template_text,
                "channel_scope": entry.channel_scope,
            },
        )


def downgrade() -> None:
    for col in (
        "button_clicks",
        "subscribers_at_publication",
        "views_7d",
        "views_72h",
        "views_48h",
        "views_24h",
        "views_3h",
        "views_1h",
    ):
        op.drop_column("post_metrics", col)
    op.drop_column("processed_posts", "article_meta")
    op.drop_column("channels", "topic_queue")
