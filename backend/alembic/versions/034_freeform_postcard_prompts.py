"""Give postcard image generation ChatGPT-like freedom.

Importers: Alembic ``upgrade head`` during deployment.
Affected data: updates four postcard prompt templates so the image path
receives a minimal user-style request and the caption names the occasion.

Revision ID: 034
Revises: 033
Create Date: 2026-07-27
"""

import json

import sqlalchemy as sa

from alembic import op

revision = "034"
down_revision = "033"
branch_labels = None
depends_on = None

_BACKUP_NAME = "pre_freeform_postcards_20260727"
_UPDATED_KEYS = (
    "writing.postcard",
    "writing.system_postcard",
    "image.writer_hint_postcard",
    "image.cover_prompt_postcard",
)

_NEW_PROMPTS: dict[str, dict[str, object]] = {
    "writing.postcard": {
        "name": "Написание открытки",
        "description": "Отдельный промпт для канала открыток (не аппенд к статейному)",
        "template_variables": [
            "channel_name",
            "channel_niche",
            "topic",
            "angle",
            "teaser_max_length",
            "image_guidelines",
        ],
        "template_text": (
            'Ты — автор коротких открыток для Telegram-канала «{channel_name}».\n'
            "Характер канала: {channel_niche}\n"
            "\n"
            "Повод/тема: {topic}\n"
            "Настроение: {angle}\n"
            "\n"
            "Напиши тёплое поздравление именно с этим поводом. В teaser обязательно "
            "назови повод вслух (например «С Днём работника МФЦ!» или «С добрым "
            "утром!»), без канцелярита и хэштегов. Надпись на картинке и визуал "
            "выберет генератор изображения — тебе не нужно их проектировать.\n"
            "Ответь одним JSON-объектом:\n"
            '- "title": краткое название повода для дедупликации;\n'
            '- "teaser": поздравление из 1–2 предложений с названием повода, '
            "максимум {teaser_max_length} символов, с 2–4 уместными эмодзи;\n"
            '- "body_html": короткая неповторяющая teaser фраза до 100 символов, '
            "без тегов;\n"
            '- "greeting_text": можно оставить пустым;\n'
            '- "image_prompt": {image_guidelines}'
        ),
    },
    "writing.system_postcard": {
        "name": "Системный промпт автора (Открытки)",
        "description": "Системная роль для канала открыток",
        "template_variables": [],
        "template_text": (
            "Ты автор коротких открыток-поздравлений на русском для канала "
            "«Открытки». Пиши тепло и от души, коротко — это открытка, не статья. "
            "В тексте поздравления всегда явно называй повод. "
            "Ответь только валидным JSON с ключами title, teaser, body_html, "
            "greeting_text, image_prompt."
        ),
    },
    "image.writer_hint_postcard": {
        "name": "Инструкция image_prompt (Открытки)",
        "description": (
            "Поле не используется генератором картинки — можно оставить пустым"
        ),
        "template_variables": [],
        "template_text": (
            "не используется для картинки — оставь пустую строку или короткую пометку"
        ),
    },
    "image.cover_prompt_postcard": {
        "name": "Обложка открытки (ChatGPT-подобная генерация)",
        "description": (
            "Минимальный запрос как в ChatGPT: оркестратор Responses сам "
            "додумает сюжет, типографику, логотипы и композицию"
        ),
        "template_variables": ["title"],
        "template_text": "Сделай открытку поздравление с {title}",
    },
}


def upgrade() -> None:
    """Snapshot current postcard prompts, then install freeform defaults."""
    conn = op.get_bind()
    for key in _UPDATED_KEYS:
        conn.execute(
            sa.text(
                "INSERT INTO prompt_template_backups "
                "(backup_name, prompt_key, category, name, description, "
                "template_text, template_variables, channel_scope, "
                "is_system_prompt, sort_order, source_updated_at) "
                "SELECT :backup_name, key, category, name, description, "
                "template_text, template_variables, channel_scope, "
                "is_system_prompt, sort_order, updated_at "
                "FROM prompt_templates "
                "WHERE key = :key "
                "ON CONFLICT (backup_name, prompt_key) DO NOTHING"
            ),
            {"backup_name": _BACKUP_NAME, "key": key},
        )

    for key in _UPDATED_KEYS:
        prompt = _NEW_PROMPTS[key]
        conn.execute(
            sa.text(
                "UPDATE prompt_templates "
                "SET template_text = :text, template_variables = :variables, "
                "name = :name, description = :description, "
                "updated_at = NOW() "
                "WHERE key = :key"
            ),
            {
                "key": key,
                "text": prompt["template_text"],
                "variables": json.dumps(prompt["template_variables"]),
                "name": prompt["name"],
                "description": prompt["description"],
            },
        )


def downgrade() -> None:
    """Restore only the four keys this revision changed."""
    conn = op.get_bind()
    for key in _UPDATED_KEYS:
        row = conn.execute(
            sa.text(
                "SELECT name, description, template_text, template_variables "
                "FROM prompt_template_backups "
                "WHERE backup_name = :backup_name AND prompt_key = :key"
            ),
            {"backup_name": _BACKUP_NAME, "key": key},
        ).mappings().first()
        if row is None:
            continue
        conn.execute(
            sa.text(
                "UPDATE prompt_templates "
                "SET template_text = :text, template_variables = :variables, "
                "name = :name, description = :description, "
                "updated_at = NOW() "
                "WHERE key = :key"
            ),
            {
                "key": key,
                "text": row["template_text"],
                "variables": row["template_variables"],
                "name": row["name"],
                "description": row["description"],
            },
        )
    conn.execute(
        sa.text(
            "DELETE FROM prompt_template_backups WHERE backup_name = :backup_name"
        ),
        {"backup_name": _BACKUP_NAME},
    )
