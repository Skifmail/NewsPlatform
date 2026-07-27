"""Back up and simplify postcard prompts for Responses image generation.

Importers: Alembic ``upgrade head`` during deployment.
Affected data: snapshots every postcard-scoped ``prompt_templates`` row before
updating the six templates used by the postcard ideation, writing, and image
stages.

Revision ID: 033
Revises: 032
Create Date: 2026-07-27
"""

import json

import sqlalchemy as sa

from alembic import op

revision = "033"
down_revision = "032"
branch_labels = None
depends_on = None

_BACKUP_NAME = "pre_chatgpt_postcards_20260727"
_UPDATED_KEYS = (
    "ideation.postcard",
    "ideation.manual_postcard",
    "writing.postcard",
    "writing.system_postcard",
    "image.writer_hint_postcard",
    "image.cover_prompt_postcard",
)

_NEW_PROMPTS: dict[str, dict[str, object]] = {
    "ideation.postcard": {
        "name": "Идеация повода для открытки",
        "description": "Промпт генерации повода для канала открыток",
        "template_variables": [
            "channel_name",
            "channel_niche",
            "current_date",
            "today_holiday",
            "recent_topics",
        ],
        "template_text": (
            'Канал открыток «{channel_name}». Сегодня {current_date}.\n'
            "Праздник сегодня: {today_holiday}\n"
            "\n"
            "Характер канала:\n"
            "{channel_niche}\n"
            "\n"
            "Недавние поводы, которые нельзя повторять или перефразировать:\n"
            "{recent_topics}\n"
            "\n"
            "Выбери ОДИН понятный повод для открытки. Если сегодня есть праздник — "
            "используй именно его. Иначе выбери уместный личный или "
            "повседневный повод: "
            "день рождения, доброе утро, хороший день, вечер, выходные, благодарность, "
            "поддержку, любовь или хорошее настроение. Погода сама по себе не является "
            "поводом.\n"
            "В angle передай только короткое настроение или смысловую ассоциацию. "
            "Не проектируй композицию — её выберет генератор изображения.\n"
            "\n"
            "JSON одной строкой:\n"
            '{{"topic": "повод 3–6 слов на русском", '
            '"angle": "настроение или ассоциация одной фразой", '
            '"search_queries": []}}'
        ),
    },
    "ideation.manual_postcard": {
        "name": "Идеация по ручному поводу (открытка)",
        "description": (
            "Визуальный угол для открытки на повод/праздник, заданный вручную "
            "в карточке канала"
        ),
        "template_variables": [
            "channel_name",
            "channel_niche",
            "current_date",
            "user_topic",
        ],
        "template_text": (
            'Канал открыток «{channel_name}». Сегодня {current_date}.\n'
            "\n"
            "Характер канала:\n"
            "{channel_niche}\n"
            "\n"
            "Редактор задал повод, его нельзя менять:\n"
            "{user_topic}\n"
            "\n"
            "Повтори повод дословно. В angle дай только короткое настроение или "
            "смысловую ассоциацию, не описывая композицию изображения.\n"
            "\n"
            "JSON одной строкой:\n"
            '{{"topic": "тот же повод что задал редактор", '
            '"angle": "настроение или ассоциация одной фразой", '
            '"search_queries": []}}'
        ),
    },
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
            "Напиши тёплый, живой текст без канцелярских клише и хэштегов. Ответь "
            "одним JSON-объектом:\n"
            '- "title": краткое название повода для дедупликации;\n'
            '- "teaser": основное пожелание из 1–2 предложений, максимум '
            "{teaser_max_length} символов, с 2–4 уместными эмодзи;\n"
            '- "body_html": короткая неповторяющая teaser фраза до 100 символов, '
            "без тегов;\n"
            '- "greeting_text": естественная надпись для картинки на русском, '
            "2–6 слов;\n"
            '- "image_prompt": {image_guidelines}'
        ),
    },
    "writing.system_postcard": {
        "name": "Системный промпт автора (Открытки)",
        "description": "Системная роль для канала открыток",
        "template_variables": [],
        "template_text": (
            "Ты автор коротких открыток-поздравлений на русском для канала «Открытки». "
            "Пиши тепло и от души, коротко — это открытка, не статья. "
            "Ответь только валидным JSON с ключами title, teaser, body_html, "
            "greeting_text, image_prompt."
        ),
    },
    "image.writer_hint_postcard": {
        "name": "Инструкция image_prompt (Открытки)",
        "description": "Короткий смысловой контекст для генератора открытки",
        "template_variables": [],
        "template_text": (
            "одна короткая фраза о настроении или смысловой ассоциации повода. "
            "Не задавай объекты, композицию, стиль, палитру, освещение или "
            "расположение "
            "текста — это самостоятельно выберет генератор изображения."
        ),
    },
    "image.cover_prompt_postcard": {
        "name": "Обложка открытки (ChatGPT-подобная генерация)",
        "description": (
            "Короткая задача для Responses image_generation: повод и точная надпись"
        ),
        "template_variables": ["title", "scene", "greeting_text"],
        "template_text": (
            "Создай красивую вертикальную открытку для Telegram.\n"
            "Повод: «{title}».\n"
            "Настроение или ассоциация: {scene}.\n"
            "На изображении должна быть ровно одна надпись: «{greeting_text}».\n"
            "Сам выбери небанальный сюжет, композицию, художественный стиль, цвета и "
            "типографику, подходящие этому поводу. Надпись должна читаться без ошибок "
            "и органично входить в изображение. Не добавляй другой текст, логотипы, "
            "водяные знаки или рамки."
        ),
    },
}


def upgrade() -> None:
    """Snapshot effective postcard prompts, then install simplified defaults."""
    op.create_table(
        "prompt_template_backups",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("backup_name", sa.String(120), nullable=False),
        sa.Column("prompt_key", sa.String(120), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("template_text", sa.Text(), nullable=False),
        sa.Column("template_variables", sa.Text(), nullable=False),
        sa.Column("channel_scope", sa.String(60), nullable=False),
        sa.Column("is_system_prompt", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "backed_up_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "backup_name",
            "prompt_key",
            name="uq_prompt_template_backups_name_key",
        ),
    )

    conn = op.get_bind()
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
            "WHERE channel_scope = 'postcard' OR key LIKE '%postcard%'"
        ),
        {"backup_name": _BACKUP_NAME},
    )

    for key in _UPDATED_KEYS:
        prompt = _NEW_PROMPTS[key]
        conn.execute(
            sa.text(
                "UPDATE prompt_templates "
                "SET template_text = :text, template_variables = :variables, "
                "name = :name, description = :description "
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
    """Restore the exact effective prompts captured before this migration."""
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE prompt_templates AS current "
            "SET category = backup.category, "
            "name = backup.name, "
            "description = backup.description, "
            "template_text = backup.template_text, "
            "template_variables = backup.template_variables, "
            "channel_scope = backup.channel_scope, "
            "is_system_prompt = backup.is_system_prompt, "
            "sort_order = backup.sort_order, "
            "updated_at = backup.source_updated_at "
            "FROM prompt_template_backups AS backup "
            "WHERE backup.backup_name = :backup_name "
            "AND current.key = backup.prompt_key "
            "AND backup.prompt_key IN :keys"
        ).bindparams(sa.bindparam("keys", expanding=True)),
        {"backup_name": _BACKUP_NAME, "keys": list(_UPDATED_KEYS)},
    )
    op.drop_table("prompt_template_backups")
