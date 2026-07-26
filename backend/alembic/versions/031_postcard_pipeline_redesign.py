"""Redesign postcard pipeline prompts: holiday priority, scene library, art-director cover.

Importers: alembic upgrade head (deployment).
Affected API: PATCH/reset endpoints for the 3 updated keys + new image.cover_prompt_postcard
key surfaced by GET/PATCH/POST /api/prompts (no route changes, data-only migration).
Data schema: prompt_templates rows — updates template_text/template_variables for
ideation.postcard, writing.postcard, image.writer_hint_postcard; inserts
image.cover_prompt_postcard.
User instruction: redesign the postcard channel per the ChatGPT-derived plan — real
holiday priority instead of "seasonal" bias, per-occasion scene library instead of
flowers, and a text-preserving gpt-image-2 art-director prompt for the greeting text.

Revision ID: 031
Revises: 030
Create Date: 2026-07-26
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "031"
down_revision = "030"
branch_labels = None
depends_on = None

_UPDATED_KEYS = (
    "ideation.postcard",
    "writing.postcard",
    "image.writer_hint_postcard",
)

# Снэпшот текста ДО этой миграции (посеян миграцией 030) — для downgrade().
_OLD_TEXT = {
    "ideation.postcard": (
        'Канал открыток «{channel_name}». Сегодня {current_date}.\n'
        "\n"
        "Уже были (НЕ повторять):\n"
        "{recent_topics}\n"
        "\n"
        "Придумай ОДИН повод для открытки, подходящий текущему сезону.\n"
        "Примеры: доброе утро, хороший день, день рождения, выходные, дружба,\n"
        "любовь, «верь в себя», праздники по сезону, просто так.\n"
        "\n"
        "JSON одной строкой:\n"
        '{{"topic": "повод 3–6 слов", "angle": "настроение в 1 предложении", "search_queries": []}}'
    ),
    "writing.postcard": (
        'Ты — автор коротких открыток для Telegram-канала «{channel_name}».\n'
        "Стиль канала: {channel_niche}\n"
        "\n"
        "Повод/тема: {topic}\n"
        "\n"
        "Напиши открытку-поздравление. Ответь строго одним JSON-объектом с ключами:\n"
        "\n"
        '"title"     — краткое название повода, 3–7 слов '
        "(для внутренней дедупликации тем, в посте не показывается).\n"
        '"teaser"    — ОСНОВНОЙ ТЕКСТ ОТКРЫТКИ: 1–2 тёплых живых предложения.\n'
        "              Много уместных эмодзи (3–6 штук по тексту, не подряд друг за другом).\n"
        "              Без хэштегов. Без канцелярских клише "
        "(«поздравляем вас с этим замечательным...»).\n"
        "              Максимум {teaser_max_length} символов.\n"
        '"body_html" — ОДНА короткая строка-продолжение (до 100 символов): строчка стиха, второе\n'
        "              пожелание или тёплая фраза. Без тегов <b>/<i>. НЕ повторяет teaser.\n"
        '              Если нечего добавить — пустая строка "".\n'
        '"image_prompt" — {image_guidelines}'
    ),
    "image.writer_hint_postcard": (
        "Поле image_prompt: 2–3 предложения на английском — детальное описание "
        "праздничной открыточной картинки. "
        "1) Выбери стиль под повод: photorealistic flowers and decor with bokeh, "
        "vibrant 3D render with soft glow, lush garden scene with celebration mood, "
        "или soft digital art with glowing elements and warm bokeh. "
        "2) Цвета яркие и насыщенные: красные/розовые розы и сердечки для любви; "
        "золотые/белые для поздравлений и юбилеев; фиолетово-синие для вечера/ночи; "
        "зелёно-жёлтые для весны/утра; тёплые оранжевые/жёлтые для уюта/дружбы. "
        "3) Конкретные объекты повода: розы, тюльпаны, сердечки, звёздочки, бабочки, "
        "листья, снежинки — много, пышно, празднично. "
        "Мягкое тёплое свечение, боке на фоне, праздничная атмосфера. "
        "Композиция edge-to-edge, заполняет весь холст без полей и рамок. "
        "Без людей, лиц, текста, цифр, надписей."
    ),
}

_OLD_VARIABLES = {
    "ideation.postcard": ["channel_name", "current_date", "recent_topics"],
    "writing.postcard": [
        "channel_name", "channel_niche", "topic",
        "teaser_max_length", "image_guidelines",
    ],
    "image.writer_hint_postcard": [],
}


def upgrade() -> None:
    from app.domain.prompt_defaults import PROMPT_DEFAULTS

    conn = op.get_bind()

    for key in _UPDATED_KEYS:
        entry = PROMPT_DEFAULTS[key]
        conn.execute(
            sa.text(
                "UPDATE prompt_templates "
                "SET template_text = :text, template_variables = :vars "
                "WHERE key = :key"
            ),
            {
                "text": entry.template_text,
                "vars": json.dumps(entry.template_variables),
                "key": key,
            },
        )

    new_entry = PROMPT_DEFAULTS["image.cover_prompt_postcard"]
    conn.execute(
        sa.text(
            "INSERT INTO prompt_templates "
            "(key, category, name, description, template_text, "
            "template_variables, channel_scope, is_system_prompt, sort_order) "
            "VALUES (:key, :category, :name, :description, :template_text, "
            ":template_variables, :channel_scope, :is_system_prompt, :sort_order) "
            "ON CONFLICT (key) DO NOTHING"
        ),
        {
            "key": new_entry.key,
            "category": new_entry.category,
            "name": new_entry.name,
            "description": new_entry.description,
            "template_text": new_entry.template_text,
            "template_variables": json.dumps(new_entry.template_variables),
            "channel_scope": new_entry.channel_scope,
            "is_system_prompt": new_entry.is_system_prompt,
            "sort_order": new_entry.sort_order,
        },
    )


def downgrade() -> None:
    conn = op.get_bind()

    for key in _UPDATED_KEYS:
        conn.execute(
            sa.text(
                "UPDATE prompt_templates "
                "SET template_text = :text, template_variables = :vars "
                "WHERE key = :key"
            ),
            {
                "text": _OLD_TEXT[key],
                "vars": json.dumps(_OLD_VARIABLES[key]),
                "key": key,
            },
        )

    conn.execute(
        sa.text("DELETE FROM prompt_templates WHERE key = :key"),
        {"key": "image.cover_prompt_postcard"},
    )
