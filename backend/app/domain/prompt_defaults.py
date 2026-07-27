"""Реестр дефолтных промпт-шаблонов.

Importers: PromptService (get defaults for seeding/reset),
           Alembic migration 030 (seed prompt_templates table).
User instruction: "не нужно ничего захардкоживать" — все промпты в БД,
                  этот файл содержит только начальные значения для миграции и reset.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PromptDefaultEntry:
    """Дефолтный промпт для seed/reset."""

    key: str
    category: str
    name: str
    description: str
    template_text: str
    template_variables: list[str] = field(default_factory=list)
    channel_scope: str = "all"
    is_system_prompt: bool = False
    sort_order: int = 0


# ---------------------------------------------------------------------------
# classification
# ---------------------------------------------------------------------------

_CLASSIFICATION_USER = PromptDefaultEntry(
    key="classification.user",
    category="classification",
    name="Классификация новости",
    description="Промпт определения тематики новости (it/auto/russia/sport)",
    template_text=(
        "Определи тематику новости. Ответь ТОЛЬКО одним словом: it, auto, russia или sport.\n"
        "- it: технологии, программирование, гаджеты, интернет, AI\n"
        "- auto: автомобили, мотоциклы, ПДД, дороги, транспорт\n"
        "- russia: политика, экономика, общество, события в России\n"
        "- sport: спорт, соревнования, трансферы, матчи, олимпиада\n"
        "\n"
        "Новость: {text}"
    ),
    template_variables=["text"],
    sort_order=10,
)

_CLASSIFICATION_SYSTEM = PromptDefaultEntry(
    key="classification.system",
    category="classification",
    name="Системный промпт классификатора",
    description="Системная роль для DeepSeek при классификации новостей",
    template_text=(
        "Ты классификатор новостей. "
        "Ответь одним словом: it, auto, russia или sport."
    ),
    is_system_prompt=True,
    sort_order=20,
)

# ---------------------------------------------------------------------------
# topic_selection
# ---------------------------------------------------------------------------

_TOPIC_SELECTION_CURATED_PICK = PromptDefaultEntry(
    key="topic_selection.curated_pick",
    category="topic_selection",
    name="Отбор лучшей новости",
    description="Промпт выбора одной лучшей новости из списка кандидатов для публикации",
    template_text=(
        'Ты главный редактор Telegram-канала с тематикой «{topic_label}».\n'
        "Из списка сырых новостей выбери ОДНУ самую интересную для публикации прямо сейчас.\n"
        "\n"
        "Критерии (по убыванию важности):\n"
        "- актуальность и свежесть;\n"
        "- значимость для аудитории канала;\n"
        "- небанальность (избегай вторичных пересказов);\n"
        "- достаточно фактов для полноценного поста.\n"
        "\n"
        "Ответь строго JSON одной строкой без markdown:\n"
        '{{"id": <число id из списка>, "reason": "<1–2 предложения: почему именно эта новость>"}}\n'
        "\n"
        "Материалы:\n"
        "{candidates}"
    ),
    template_variables=["topic_label", "candidates"],
    sort_order=10,
)

_TOPIC_SELECTION_CURATED_PICK_SYSTEM = PromptDefaultEntry(
    key="topic_selection.curated_pick_system",
    category="topic_selection",
    name="Системный промпт отбора новостей",
    description="Системная роль для модели при выборе лучшей новости",
    template_text=(
        "Ты выбираешь одну лучшую новость. "
        'Ответь ТОЛЬКО JSON: {"id": число, "reason": "краткое обоснование"}. '
        "Никакого текста до или после JSON."
    ),
    is_system_prompt=True,
    sort_order=20,
)

# ---------------------------------------------------------------------------
# topic_ideation
# ---------------------------------------------------------------------------

_IDEATION_DEFAULT = PromptDefaultEntry(
    key="ideation.default",
    category="topic_ideation",
    name="Идеация темы (по умолчанию)",
    description="Основной промпт генерации темы для познавательной статьи",
    template_text=(
        'Ты — редактор познавательного Telegram-канала «{channel_name}».\n'
        "Ниша канала: {channel_niche}\n"
        "\n"
        "Недавние темы и заголовки (СТРОГО ЗАПРЕЩЕНО повторять и близкие по смыслу):\n"
        "{recent_topics}\n"
        "\n"
        "Правила выбора темы:\n"
        "- Одна конкретная концепция = одна статья. Нельзя перефразировать недавнюю тему другими словами.\n"
        "- Если недавно был «эффект плацебо» — запрещены сахарная таблетка, сила внушения, самовнушение и т.п.\n"
        "- Если недавно было «дежавю» — запрещены ложные воспоминания, déjà vu, «уже здесь были».\n"
        "- Чередуй области знаний: космос, история, биология, физика, технологии, культура, экономика, язык, археология.\n"
        "- Не выбирай подряд несколько тем из одной области (психология мозга, оптические иллюзии и т.д.).\n"
        "- Тема должна быть интересной широкой аудитории, с потенциалом для фактов из интернета.\n"
        "\n"
        "Придумай ОДНУ свежую познавательную тему для длинной статьи на русском.\n"
        "\n"
        "Ответь строго JSON одной строкой:\n"
        '{{"topic": "краткое название темы", "angle": "угол подачи в 1-2 предложения", '
        '"search_queries": ["запрос 1", "запрос 2", "запрос 3"]}}'
    ),
    template_variables=["channel_name", "channel_niche", "recent_topics"],
    sort_order=10,
)

_IDEATION_POSTCARD = PromptDefaultEntry(
    key="ideation.postcard",
    category="topic_ideation",
    name="Идеация повода для открытки",
    description="Промпт генерации повода для канала открыток",
    template_text=(
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
        "используй именно его. Иначе выбери уместный личный или повседневный повод: "
        "день рождения, доброе утро, хороший день, вечер, выходные, благодарность, "
        "поддержку, любовь или хорошее настроение. Погода сама по себе не является "
        "поводом.\n"
        "В angle передай только короткое настроение или смысловую ассоциацию. "
        "Не проектируй композицию — её выберет генератор изображения.\n"
        "\n"
        "JSON одной строкой:\n"
        '{{"topic": "повод 3–6 слов на русском", '
        '"angle": "настроение или ассоциация одной фразой", "search_queries": []}}'
    ),
    template_variables=[
        "channel_name", "channel_niche", "current_date",
        "today_holiday", "recent_topics",
    ],
    channel_scope="postcard",
    sort_order=20,
)

_IDEATION_MANUAL_TOPIC = PromptDefaultEntry(
    key="ideation.manual_topic",
    category="topic_ideation",
    name="Идеация по ручной теме (статья)",
    description=(
        "Угол подачи и поисковые запросы для статьи на тему, заданную вручную "
        "в карточке канала"
    ),
    template_text=(
        'Ты — редактор познавательного Telegram-канала «{channel_name}».\n'
        "Ниша канала: {channel_niche}\n"
        "\n"
        "Тема статьи ЗАДАНА вручную редактором и НЕ должна меняться:\n"
        "{user_topic}\n"
        "\n"
        "Задача: НЕ придумывай другую тему. Подготовь угол подачи и поисковые\n"
        "запросы именно для этой темы.\n"
        "\n"
        "Правила:\n"
        "- Поле topic в JSON должно дословно повторять заданную тему.\n"
        "- angle — угол подачи в 1–2 предложениях: что раскрыть, какой крючок.\n"
        "- search_queries — ровно 3 конкретных запроса на русском для веб-поиска\n"
        "  фактов и контекста по этой теме.\n"
        "\n"
        "Ответь строго JSON одной строкой:\n"
        '{{"topic": "та же тема что задал редактор", '
        '"angle": "угол подачи в 1-2 предложения", '
        '"search_queries": ["запрос 1", "запрос 2", "запрос 3"]}}'
    ),
    template_variables=["channel_name", "channel_niche", "user_topic"],
    sort_order=21,
)

_IDEATION_MANUAL_POSTCARD = PromptDefaultEntry(
    key="ideation.manual_postcard",
    category="topic_ideation",
    name="Идеация по ручному поводу (открытка)",
    description=(
        "Визуальный угол для открытки на повод/праздник, заданный вручную "
        "в карточке канала"
    ),
    template_text=(
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
    template_variables=[
        "channel_name", "channel_niche", "current_date", "user_topic",
    ],
    channel_scope="postcard",
    sort_order=22,
)

_IDEATION_SYSTEM_DEFAULT = PromptDefaultEntry(
    key="ideation.system_default",
    category="topic_ideation",
    name="Системный промпт идеации (по умолчанию)",
    description="Системная роль для генерации тем статей",
    template_text=(
        "Ты придумываешь темы для познавательных статей. "
        "Никогда не повторяй и не перефразируй недавние темы. "
        "Ответь только JSON с полями topic, angle, search_queries."
    ),
    is_system_prompt=True,
    sort_order=30,
)

_IDEATION_SYSTEM_POSTCARD = PromptDefaultEntry(
    key="ideation.system_postcard",
    category="topic_ideation",
    name="Системный промпт идеации (открытки)",
    description="Системная роль для генерации поводов открыток",
    template_text="Ты придумываешь поводы для открыток. Ответь JSON.",
    channel_scope="postcard",
    is_system_prompt=True,
    sort_order=40,
)

_IDEATION_SYSTEM_PARAGRAPH = PromptDefaultEntry(
    key="ideation.system_paragraph",
    category="topic_ideation",
    name="Системный промпт идеации (Параграф)",
    description="Системная роль для генерации тем канала Параграф",
    template_text=(
        "Ты придумываешь темы для познавательных статей. "
        "Никогда не повторяй и не перефразируй недавние темы. "
        "Ответь только JSON с полями topic, angle, search_queries. "
        "Для канала «Параграф» чередуй разные области знаний — "
        "не предлагай подряд психологию мозга и когнитивные эффекты."
    ),
    channel_scope="paragraph",
    is_system_prompt=True,
    sort_order=50,
)

_IDEATION_DEVTOOLS_EXTRA = PromptDefaultEntry(
    key="ideation.devtools_extra",
    category="topic_ideation",
    name="Доп. инструкции идеации (GitHub находки)",
    description=(
        "Общие правила отбора репозитория для devtools-канала. "
        "Дополняется одним из двух блоков ниже — в зависимости от того, "
        "удалось ли получить живой список GitHub Trending."
    ),
    template_text=(
        "Канал — подборка находок с GitHub. "
        "Тема = один конкретный репозиторий (не обзор «топ-10»).\n"
        "Отбирай только то, что зацепит широкую техно-аудиторию и что "
        "хочется переслать. Приоритет:\n"
        "- популярные или трендовые репозитории (тысячи звёзд или бурный "
        "рост в последние недели);\n"
        "- ИИ/LLM/агенты, кодинг-ассистенты, интеграции с Claude Code / "
        "Cursor / Codex;\n"
        "- потребительские open-source приложения и «бесплатная "
        "альтернатива <известному продукту>» (CapCut, Notion, Postman и т.п.).\n"
        "Избегай узких CLI-утилит без явного вау и безвестных обёрток — "
        "из двух проектов выбирай более популярный и понятный.\n"
        "РАЗНООБРАЗИЕ: не бери инструмент с той же задачей, что уже был в "
        "последних постах (список недавних тем выше). Не более 1 AI/LLM-"
        "инструмента из 3 подряд — если последние посты были про AI/агентов/"
        "экономию токенов, выбери НЕ-AI категорию (CLI, self-hosted, базы, "
        "сеть, мониторинг, редакторы, форматы данных).\n"
        "ПРАВДИВОСТЬ: формат «альтернатива X» используй только если X — реально "
        "существующий продукт. Не выдумывай продукты для сравнения (нет продукта "
        "«Claude Design» и т.п.)."
    ),
    channel_scope="devtools",
    sort_order=60,
)

_IDEATION_DEVTOOLS_WITH_REPOS = PromptDefaultEntry(
    key="ideation.devtools_with_repos",
    category="topic_ideation",
    name="Идеация GitHub: живой список трендов доступен",
    description=(
        "Добавляется к общим правилам, когда удалось получить GitHub Trending. "
        "Переменная {repos_block} — сам список репозиториев, его собирает код "
        "из живых данных."
    ),
    template_text=(
        "Ниже — ЖИВОЙ список трендовых репозиториев GitHub прямо сейчас. "
        "Выбери РОВНО ОДИН из этого списка (не выдумывай свой), тот, что "
        "будет интереснее всего аудитории и ещё не выходил в канале.\n"
        "{repos_block}\n"
        "\n"
        'Поле topic — «owner/repo: суть», в angle укажи, чем цепляет. '
        "В search_queries укажи запросы именно про выбранный репозиторий: "
        '"<repo> github", "<repo> features", "<repo> alternative".'
    ),
    template_variables=["repos_block"],
    channel_scope="devtools",
    sort_order=61,
)

_IDEATION_DEVTOOLS_NO_REPOS = PromptDefaultEntry(
    key="ideation.devtools_no_repos",
    category="topic_ideation",
    name="Идеация GitHub: трендов нет, выбор из знаний модели",
    description=(
        "Фолбэк: добавляется к общим правилам, когда GitHub Trending недоступен "
        "или все трендовые репозитории уже выходили в канале."
    ),
    template_text=(
        "В search_queries обязательно добавь запросы, подтверждающие "
        "актуальность и популярность, например: "
        '"<repo> github stars", "<repo> github trending 2026", '
        '"<repo> open source alternative".'
    ),
    channel_scope="devtools",
    sort_order=62,
)

_IDEATION_PARAGRAPH_EXTRA = PromptDefaultEntry(
    key="ideation.paragraph_extra",
    category="topic_ideation",
    name="Доп. инструкции идеации (Параграф)",
    description="Дополнительные правила разнообразия тем для канала Параграф",
    template_text=(
        'Канал «Параграф» — познавательные статьи для широкой аудитории.\n'
        "\n"
        "Обязательно:\n"
        "- Тема из ДРУГОЙ области, чем последние 3–5 статей в списке выше.\n"
        "- Запрещены синонимы и перефразировки недавних тем "
        "(плацебо ≠ сахарная таблетка ≠ сила внушения).\n"
        "- Хорошие области для разнообразия: космос, древний мир, животные, "
        "физика, язык, архитектура,\n"
        "  экономические парадоксы, редкие профессии, географические аномалии, изобретения.\n"
        "- Плохо: подряд несколько статей про мозг, память, иллюзии, плацебо, дежавю, сны.\n"
        "\n"
        "Баланс (смотри список недавних тем выше):\n"
        "- ГЕОГРАФИЯ: не бери страну/регион, уже мелькавшие в последних темах. Особенно\n"
        "  не зацикливайся на одной стране (например Япония) — если она уже была недавно,\n"
        "  выбери другую часть света или тему без гео-привязки.\n"
        "- СУБЪЕКТ: не бери того же героя (животное, здание, явление, изобретение), что\n"
        "  уже был недавно, даже под другим названием (шмель ≠ пчела-нарушитель;\n"
        "  пирамиды Гизы ≠ пирамиды Амазонии).\n"
        "- ЗАГОЛОВОК: разнообразь зачин. Если последние 2–3 заголовка начинались с\n"
        '  «Почему» — начни иначе (факт-парадокс, «Как…», число, утверждение, вопрос без\n'
        '  «почему»). Не более чем каждый третий заголовок может начинаться с «Почему».'
    ),
    channel_scope="paragraph",
    sort_order=70,
)

# ---------------------------------------------------------------------------
# rewriting
# ---------------------------------------------------------------------------

_REWRITE_DEFAULT = PromptDefaultEntry(
    key="rewrite.default",
    category="rewriting",
    name="Рерайт новости",
    description="Основной шаблон рерайта новости для Telegram-канала",
    template_text=(
        'Ты — редактор Telegram-канала "{channel_name}" с тематикой "{topic_label}".\n'
        "Дополнительный стиль: {style_prompt}\n"
        "\n"
        "Перепиши новость для публикации в канале. Объём: до {max_length} символов.\n"
        "\n"
        "СТРУКТУРА (строго, каждый блок — отдельный фрагмент, между блоками пустая строка):\n"
        "\n"
        "1) Заголовок-выжимка:\n"
        "<b>Главная мысль новости одной фразой</b>\n"
        "\n"
        "2) Лид — 2-3 предложения сути:\n"
        "Кратко что произошло. Можно 1 уместный эмодзи \U0001f1f7\U0001f1fa \U0001f4f1 \U0001f697\n"
        "\n"
        "3) Цитата — ОТДЕЛЬНЫЙ блок:\n"
        "<blockquote expandable>«Прямая цитата или ключевая фраза из новости» — имя/должность</blockquote>\n"
        "Если прямой цитаты нет — вынеси главный тезис в blockquote.\n"
        "\n"
        "4) Контекст — 2-4 предложения (фон, цифры, последствия).\n"
        "\n"
        "5) Вовлечение — вопрос или призыв к обсуждению ... \U0001f914\n"
        "\n"
        "6) Ссылка на источник (если URL задан):\n"
        '<a href="{source_url}">Читать в источнике →</a>\n'
        "\n"
        "Правила оформления:\n"
        "- Только теги: b, blockquote, a, i (i — только внутри blockquote при необходимости)\n"
        "- ЗАПРЕЩЕНО: тег <p> (Telegram Bot API его не принимает)\n"
        "- Между блоками 1-2 — пустая строка, не <br> внутри одного абзаца\n"
        "- Без вводных «Итак», «Таким образом»\n"
        "- Без хэштегов (добавятся при публикации)\n"
        "- Сохрани факты, перепиши своими словами под аудиторию канала\n"
        "- Отвечай ТОЛЬКО HTML-текстом поста, без пояснений\n"
        "\n"
        "Ссылка на источник: {source_url_display}\n"
        "\n"
        "Оригинальная новость:\n"
        "{original_text}"
    ),
    template_variables=[
        "channel_name", "topic_label", "style_prompt", "max_length",
        "source_url", "source_url_display", "original_text",
    ],
    sort_order=10,
)

_REWRITE_SYSTEM = PromptDefaultEntry(
    key="rewrite.system",
    category="rewriting",
    name="Системный промпт рерайтера",
    description="Системная роль для DeepSeek при рерайте новостей",
    template_text=(
        "Ты редактор Telegram-канала. Пиши блочно: абзацы через пустую строку, "
        "без тега <p>. Цитаты только в <blockquote expandable>. "
        "Стиль — как у крупных новостных каналов: заголовок, лид, цитата, контекст, вопрос. "
        "Отвечай ТОЛЬКО готовым HTML поста. Никогда не выводи черновики, анализ фактов "
        "или пояснения к заданию."
    ),
    is_system_prompt=True,
    sort_order=20,
)

_REWRITE_STRICT_RETRY = PromptDefaultEntry(
    key="rewrite.strict_retry_suffix",
    category="rewriting",
    name="Суффикс повторного запроса рерайта",
    description="Добавляется к промпту при повторной попытке, если первый ответ был некорректен",
    template_text=(
        "\n\nКРИТИЧНО: в ответе только финальный HTML поста для Telegram. "
        "Без анализа, без списков фактов, без markdown, без рассуждений."
    ),
    sort_order=30,
)

# ---------------------------------------------------------------------------
# article_writing
# ---------------------------------------------------------------------------

_WRITING_DEFAULT = PromptDefaultEntry(
    key="writing.default",
    category="article_writing",
    name="Написание статьи (по умолчанию)",
    description="Основной шаблон для генерации познавательной статьи",
    template_text=(
        'Ты — автор познавательных статей для Telegram-канала «{channel_name}».\n'
        "Стиль канала: {channel_niche}\n"
        "\n"
        'Напиши статью на русском по теме «{topic}» ({angle}).\n'
        "Используй ТОЛЬКО факты из блока «Исследование» ниже. Не выдумывай цитаты и цифры.\n"
        "\n"
        'Структура body_html (без служебных меток «Крючок», «Вывод», «Лид», «Источники» '
        "— только содержательные подзаголовки):\n"
        "1) Лид — 2-3 предложения (без заголовка «Лид»)\n"
        "2) 3-5 разделов с подзаголовками <b>...</b> по теме\n"
        "3) Заключительный абзац — 2-3 предложения (без заголовка «Вывод»)\n"
        '4) Ссылки на источники — список <a href="...">название</a> (без заголовка «Источники»)\n'
        "\n"
        "HTML в body_html: только теги b, i, a, blockquote. Без <p>. "
        "Абзацы — через \\n\\n внутри строки JSON.\n"
        "Объём body_html: {min_length}–{max_length} символов.\n"
        "Teaser (анонс для Telegram): до {teaser_max_length} символов, "
        "интригует, без спойлеров всей статьи.\n"
        "\n"
        "Правила обложки (поле image_prompt, только английский):\n"
        "{image_guidelines}\n"
        "\n"
        "image_prompt — 1–2 предложения: ОДНА конкретная визуальная метафора инструмента или темы.\n"
        "Запрещено: нейросети, матричный дождь, голограммы, множество окон, нечитаемый код, "
        "любой текст на картинке.\n"
        "\n"
        "Ответь строго одним JSON-объектом с ключами title, teaser, body_html, image_prompt.\n"
        "\n"
        "Исследование:\n"
        "{research_context}"
    ),
    template_variables=[
        "channel_name", "channel_niche", "topic", "angle",
        "min_length", "max_length", "teaser_max_length",
        "image_guidelines", "research_context",
    ],
    sort_order=10,
)

_WRITING_POSTCARD = PromptDefaultEntry(
    key="writing.postcard",
    category="article_writing",
    name="Написание открытки",
    description="Отдельный промпт для канала открыток (не аппенд к статейному)",
    template_text=(
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
        '- "teaser": поздравление из 1–2 предложений с названием повода, максимум '
        "{teaser_max_length} символов, с 2–4 уместными эмодзи;\n"
        '- "body_html": короткая неповторяющая teaser фраза до 100 символов, без тегов;\n'
        '- "greeting_text": можно оставить пустым;\n'
        '- "image_prompt": {image_guidelines}'
    ),
    template_variables=[
        "channel_name", "channel_niche", "topic", "angle",
        "teaser_max_length", "image_guidelines",
    ],
    channel_scope="postcard",
    sort_order=20,
)

_WRITING_SYSTEM_DEFAULT = PromptDefaultEntry(
    key="writing.system_default",
    category="article_writing",
    name="Системный промпт автора статей",
    description="Системная роль для генерации познавательных статей",
    template_text=(
        "Ты автор познавательных статей на русском. "
        "Пиши увлекательно, но строго по фактам из исследования. "
        "Ответь только валидным JSON с ключами title, teaser, body_html, image_prompt."
    ),
    is_system_prompt=True,
    sort_order=30,
)

_WRITING_SYSTEM_DEVTOOLS = PromptDefaultEntry(
    key="writing.system_devtools",
    category="article_writing",
    name="Системный промпт автора (GitHub находки)",
    description="Системная роль для карточек GitHub-находок",
    template_text=(
        "Ты автор карточек GitHub-находок на русском. "
        "Строго по фактам из исследования — не выдумывай stars, forks и язык. "
        "Крючок (hook) — разный заход в каждой карточке; "
        "не начинай с «Устали от» и похожих шаблонов. "
        "Ответь только валидным JSON с ключами: title, teaser, body_html, image_prompt, "
        "project_name, repo_url, language, stars, forks, hook, features, insight."
    ),
    channel_scope="devtools",
    is_system_prompt=True,
    sort_order=40,
)

_WRITING_SYSTEM_PARAGRAPH = PromptDefaultEntry(
    key="writing.system_paragraph",
    category="article_writing",
    name="Системный промпт автора (Параграф)",
    description="Системная роль для канала Параграф",
    template_text=(
        "Ты автор познавательных статей на русском для канала «Параграф». "
        "Пиши увлекательно, но строго по фактам из исследования. "
        "Ответь только валидным JSON с ключами: title, teaser, body_html, image_prompt, "
        "hook, quote, closing."
    ),
    channel_scope="paragraph",
    is_system_prompt=True,
    sort_order=50,
)

_WRITING_SYSTEM_POSTCARD = PromptDefaultEntry(
    key="writing.system_postcard",
    category="article_writing",
    name="Системный промпт автора (Открытки)",
    description="Системная роль для канала открыток",
    template_text=(
        "Ты автор коротких открыток-поздравлений на русском для канала «Открытки». "
        "Пиши тепло и от души, коротко — это открытка, не статья. "
        "В тексте поздравления всегда явно называй повод. "
        "Ответь только валидным JSON с ключами title, teaser, body_html, "
        "greeting_text, image_prompt."
    ),
    channel_scope="postcard",
    is_system_prompt=True,
    sort_order=60,
)

_WRITING_DEVTOOLS_INSTRUCTIONS = PromptDefaultEntry(
    key="writing.devtools_instructions",
    category="article_writing",
    name="Инструкции формата (GitHub находки)",
    description=(
        "Доп. инструкции для ArticleWriter при генерации карточки devtools. "
        "Переменная {anti_repeat} заполняется оркестратором из недавних крючков."
    ),
    template_text=(
        "Формат Telegram-анонса (поле teaser соберёт платформа — заполни структурные поля):\n"
        "\n"
        "Ответь JSON с ключами:\n"
        "title, body_html, image_prompt,\n"
        "project_name, repo_url, language, stars, forks, hook, features, insight.\n"
        "\n"
        "- project_name — короткое имя репозитория/утилиты (openscreen, mise, duckdb).\n"
        "- repo_url — прямая ссылка на GitHub/GitLab (обязательно для превью в Telegram).\n"
        "- language — основной язык (#TypeScript, Rust, Go…) — только из исследования.\n"
        '- stars, forks — как на GitHub (3.1k, 174) — только если есть в исследовании, иначе «—».\n'
        "- hook — 1–2 предложения: цепляющий вход в карточку, живо, без кликбейта.\n"
        "  ГЛАВНОЕ ПРАВИЛО: hook ОБЯЗАН описывать реальную задачу, сценарий или\n"
        "  возможность именно этого инструмента (project_name). Он должен быть проверяем\n"
        "  по полям features/insight/title — любой факт, метрика или сравнение в hook\n"
        "  должны либо повторять то, что ты сам написал в features/insight, либо прямо\n"
        "  следовать из исследования. ЗАПРЕЩЕНО придумывать сравнения с другими\n"
        "  инструментами, цифры экономии токенов/времени, «X использует N токенов,\n"
        "  Y — M» и любую статистику, которой нет в исследовании. Если hook невозможно\n"
        "  проверить по features/insight — перепиши его.\n"
        "  Чередуй форматы (каждый пост — другой тип захода):\n"
        "  • факт/новость: «Cloudflare открыли свой прокси-фреймворк на Rust»\n"
        "  • контраст: «Вместо awk/sed — таблицы и JSON из коробки»\n"
        "  • вопрос: «Как передать файл без облака и регистрации?»\n"
        "  • возможность: «Мониторинг CPU и стресс-тест в одном TUI»\n"
        "  • сценарий: «Закоммитили ключ — инструмент найдёт его в истории Git»\n"
        "  ЗАПРЕЩЕНО начинать hook с: «Устали от», «Устали», «Замучились», «Надоело» "
        "— это шаблон ИИ.\n"
        "  Эмодзи в hook — не больше одного; платформа сама добавит \U0001f3ac перед текстом.\n"
        "- features — массив из 3–5 коротких пунктов «что умеет».\n"
        "- insight — 1 предложение «кому зайдёт / в чём фишка» (\U0001f4a1).\n"
        '- teaser — оставь пустой строкой "" (соберём автоматически).{anti_repeat}\n'
        "\n"
        "body_html — основной текст для публикации в Telegram (не Telegraph): развёрнутый обзор.\n"
        "Ориентир объёма body_html — поле max_length в основном промпте.\n"
        "\n"
        "ВАЖНО (переопределяет структуру основного промпта для этого канала):\n"
        "НЕ добавляй в конце body_html вопрос-вовлечение к читателю и эмодзи \U0001f447\n"
        "(«А вы готовы…?», «А вы пробовали…?» и т.п.). Заверши body_html содержательным\n"
        "выводом и списком ссылок на источники — без вопроса и без призыва к действию."
    ),
    template_variables=["anti_repeat"],
    channel_scope="devtools",
    sort_order=70,
)

_WRITING_PARAGRAPH_INSTRUCTIONS = PromptDefaultEntry(
    key="writing.paragraph_instructions",
    category="article_writing",
    name="Инструкции формата (Параграф)",
    description="Доп. инструкции для ArticleWriter при генерации статьи Параграф",
    template_text=(
        "Формат Telegram-анонса (поле teaser соберёт платформа — заполни структурные поля):\n"
        "\n"
        "Ответь JSON с ключами:\n"
        "title, body_html, image_prompt, hook, quote, closing.\n"
        "\n"
        "- hook — 2–3 предложения-крючок; начни с 1 уместного эмодзи "
        "(\U0001f9e0 \U0001f4a1 \U0001f52c ✨ \U0001f9ea).\n"
        "- quote — короткая яркая цитата или ключевая фраза из исследования "
        "(только реальные факты).\n"
        "- closing — 1–2 предложения интриги, без спойлеров всей статьи.\n"
        '- teaser — оставь пустой строкой "" (соберём автоматически).\n'
        "\n"
        "body_html — основной текст для публикации в Telegram (не Telegraph): развёрнутая статья.\n"
        "ЗАПРЕЩЕНО в body_html использовать служебные заголовки разделов:\n"
        "«Крючок», «Hook», «Quote», «Цитата», «Closing», «Вывод», «Лид», "
        "«Неожиданный поворот»,\n"
        "«Источники» и другие метки из этого списка полей JSON.\n"
        "Содержимое hook/quote/closing — ТОЛЬКО в соответствующих JSON-полях, "
        "не дублируй в body_html.\n"
        "Подзаголовки разделов — осмысленные формулировки по теме (<b>...</b>), "
        "не названия полей промпта.\n"
        "\n"
        "image_prompt — только английский, 3–4 предложения.\n"
        "Опиши детальную образовательную иллюстрацию с конкретными объектами из статьи:\n"
        "точные предметы, научные элементы, материалы и текстуры, ракурс, "
        "освещение (мягкий студийный или натуральный), цветовая палитра.\n"
        "Стиль: photorealism или high-quality 3D render, насыщенный деталями, "
        "передающий суть темы.\n"
        "Абсолютно запрещено: люди, лица, тела, текст / буквы / цифры на изображении, "
        "интерфейсы, экраны.\n"
        "Лимит карточки teaser после сборки: до {teaser_max_length} символов."
    ),
    template_variables=["teaser_max_length"],
    channel_scope="paragraph",
    sort_order=80,
)

# ---------------------------------------------------------------------------
# image_prompts
# ---------------------------------------------------------------------------

_IMAGE_WRITER_HINT_DEFAULT = PromptDefaultEntry(
    key="image.writer_hint_default",
    category="image_prompts",
    name="Инструкция image_prompt (по умолчанию)",
    description="Инструкция для поля image_prompt в ArticleWriter — физическая метафора",
    template_text=(
        "Поле image_prompt: одно предложение на английском — ОДИН конкретный "
        "осязаемый объект или сцена как визуальная метафора работы инструмента "
        "(например, для файлового менеджера — папка-дерево с лупой). Только "
        "физические предметы и формы. НЕ упоминай файлы с текстом, код, команды, "
        "терминал, интерфейс, экраны, надписи и названия — Qwen рисует их буквально "
        "текстом на картинке."
    ),
    sort_order=10,
)

_IMAGE_WRITER_HINT_POSTCARD = PromptDefaultEntry(
    key="image.writer_hint_postcard",
    category="image_prompts",
    name="Инструкция image_prompt (Открытки)",
    description="Поле не используется генератором картинки — можно оставить пустым",
    template_text=(
        "не используется для картинки — оставь пустую строку или короткую пометку"
    ),
    channel_scope="postcard",
    sort_order=20,
)

_IMAGE_WRITER_HINT_PARAGRAPH = PromptDefaultEntry(
    key="image.writer_hint_paragraph",
    category="image_prompts",
    name="Инструкция image_prompt (Параграф)",
    description="Инструкция для обложки Параграф — описание содержания, не картинки",
    template_text=(
        "Поле image_prompt: 5–7 предложений НА РУССКОМ — краткая суть статьи: "
        "о чём она, какие главные факты, почему это интересно читателю. "
        "Это описание пойдёт в генератор обложки, который сам выберет визуальный стиль, "
        "цвета и композицию. НЕ описывай картинку — опиши СОДЕРЖАНИЕ статьи."
    ),
    channel_scope="paragraph",
    sort_order=30,
)

_IMAGE_LOGO_EDIT_TEMPLATE = PromptDefaultEntry(
    key="image.logo_edit_template",
    category="image_prompts",
    name="Стилизация логотипа (Qwen Edit)",
    description="Шаблон для Qwen Image Edit — размещение логотипа на фоне",
    template_text=(
        "Place this logo as the clear centered hero on a smooth dark navy background "
        "with soft studio lighting and a subtle glow. Around it arrange a few small "
        "elegant minimalist 3D shapes suggesting {scene}, kept subtle and secondary "
        "to the logo. Premium modern product render, generous empty space, tasteful, "
        "keep the logo clean, sharp and unchanged."
    ),
    template_variables=["scene"],
    channel_scope="devtools",
    sort_order=40,
)

_IMAGE_COVER_PROMPT = PromptDefaultEntry(
    key="image.cover_prompt",
    category="image_prompts",
    name="Журнальная обложка (gpt-image-2)",
    description="Шаблон промпта обложки-иллюстрации для канала Параграф",
    template_text=(
        "Ты — арт-директор журнала. Создай обложку-иллюстрацию к статье.\n"
        "\n"
        "Заголовок статьи: «{title}»\n"
        "\n"
        "Суть статьи: {summary}\n"
        "\n"
        "Требования к обложке:\n"
        "1. Формат: широкий 16:9 (landscape).\n"
        "2. Драматичная, кинематографичная фоновая иллюстрация-метафора "
        "по теме статьи — конкретные предметы, текстуры, глубина.\n"
        "3. Крупный заголовок «{title}» — "
        "типографика должна гармонировать с цветовой палитрой иллюстрации. "
        "Выбери цвет, шрифт, тень и расположение текста сам — "
        "главное, чтобы текст читался и выглядел как часть журнальной обложки.\n"
        "4. Под заголовком — короткая цитата или подзаголовок из статьи "
        "(1 предложение) контрастным акцентным цветом, меньшим шрифтом.\n"
        "5. Без людей, лиц, UI-рамок, водяных знаков."
    ),
    template_variables=["title", "summary"],
    channel_scope="paragraph",
    sort_order=50,
)

_IMAGE_COVER_PROMPT_POSTCARD = PromptDefaultEntry(
    key="image.cover_prompt_postcard",
    category="image_prompts",
    name="Обложка открытки (gpt-image-2)",
    description=(
        "Короткий запрос для прямой генерации открытки через gpt-image-2"
    ),
    template_text="Сделай открытку поздравление с {title}",
    template_variables=["title"],
    channel_scope="postcard",
    sort_order=60,
)

# ---------------------------------------------------------------------------
# image_negatives
# ---------------------------------------------------------------------------

_NEGATIVE_QWEN_NO_TEXT = PromptDefaultEntry(
    key="negative.qwen_no_text",
    category="image_negatives",
    name="Негатив Qwen: без текста",
    description="Общий негативный промпт Qwen — запрет текста, рамок, тех-клише",
    template_text=(
        "text, letters, words, numbers, typography, caption, headline, title, subtitle, "
        "label, watermark, logo, banner, sign, poster with writing, speech bubble, "
        "channel name, app icon, telegram logo, science-pop, audience, "
        "frame, border, rounded rectangle, rounded square, card, UI card, "
        "thumbnail frame, thumbnail card, picture-in-picture, inset panel, "
        "framed image, image inside a frame, translucent overlay, glass panel, "
        "floating window, glassmorphism panel, vignette box, "
        "circuit board, PCB, circuit traces, printed circuit, motherboard, "
        "microchip pattern, chip traces, tech grid, glowing wires, data streams, "
        "matrix code rain, cyberpunk, neon grid, hologram, holographic HUD, "
        "sci-fi interface, futuristic dashboard, busy techy background, "
        "Cyrillic, Latin alphabet, Chinese characters, gibberish text, "
        "low resolution, low quality, distorted limbs, malformed fingers, "
        "oversaturated colors, blurry."
    ),
    sort_order=10,
)

_NEGATIVE_QWEN_NEWS = PromptDefaultEntry(
    key="negative.qwen_news",
    category="image_negatives",
    name="Негатив Qwen: новости",
    description="Негативный промпт для обложек новостей — без текста + без портретов",
    template_text=(
        "text, letters, words, numbers, typography, caption, headline, title, subtitle, "
        "label, watermark, logo, banner, sign, poster with writing, speech bubble, "
        "channel name, app icon, telegram logo, science-pop, audience, "
        "frame, border, rounded rectangle, rounded square, card, UI card, "
        "thumbnail frame, thumbnail card, picture-in-picture, inset panel, "
        "framed image, image inside a frame, translucent overlay, glass panel, "
        "floating window, glassmorphism panel, vignette box, "
        "circuit board, PCB, circuit traces, printed circuit, motherboard, "
        "microchip pattern, chip traces, tech grid, glowing wires, data streams, "
        "matrix code rain, cyberpunk, neon grid, hologram, holographic HUD, "
        "sci-fi interface, futuristic dashboard, busy techy background, "
        "Cyrillic, Latin alphabet, Chinese characters, gibberish text, "
        "low resolution, low quality, distorted limbs, malformed fingers, "
        "oversaturated colors, blurry., "
        "portrait, headshot, close-up face, generic man, generic woman, stock photo person, "
        "news anchor, reporter, businessman, office worker, person looking at camera, "
        "selfie, mugshot, passport photo."
    ),
    channel_scope="news",
    sort_order=20,
)

_NEGATIVE_QWEN_LOGO_EDIT = PromptDefaultEntry(
    key="negative.qwen_logo_edit",
    category="image_negatives",
    name="Негатив Qwen: стилизация логотипа",
    description="Негативный промпт для Qwen Image Edit при стилизации логотипа",
    template_text=(
        "blurry, low quality, distorted logo, unrecognizable brand, "
        "cluttered background, extra watermark, random gibberish text, "
        "multiple competing logos, meme style, oversaturated, ugly composition, "
        "circuit board, PCB, circuit traces, printed circuit, motherboard, "
        "microchip pattern, chip traces, tech grid, glowing wires, data streams, "
        "matrix code rain, cyberpunk, neon grid, hologram, holographic HUD, "
        "sci-fi interface, futuristic dashboard, busy techy background, "
        "frame, border, rounded rectangle, card, thumbnail frame, "
        "picture-in-picture, translucent overlay."
    ),
    channel_scope="devtools",
    sort_order=30,
)

# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

PROMPT_DEFAULTS: dict[str, PromptDefaultEntry] = {
    entry.key: entry
    for entry in [
        # classification
        _CLASSIFICATION_USER,
        _CLASSIFICATION_SYSTEM,
        # topic_selection
        _TOPIC_SELECTION_CURATED_PICK,
        _TOPIC_SELECTION_CURATED_PICK_SYSTEM,
        # topic_ideation
        _IDEATION_DEFAULT,
        _IDEATION_POSTCARD,
        _IDEATION_MANUAL_TOPIC,
        _IDEATION_MANUAL_POSTCARD,
        _IDEATION_SYSTEM_DEFAULT,
        _IDEATION_SYSTEM_POSTCARD,
        _IDEATION_SYSTEM_PARAGRAPH,
        _IDEATION_DEVTOOLS_EXTRA,
        _IDEATION_DEVTOOLS_WITH_REPOS,
        _IDEATION_DEVTOOLS_NO_REPOS,
        _IDEATION_PARAGRAPH_EXTRA,
        # rewriting
        _REWRITE_DEFAULT,
        _REWRITE_SYSTEM,
        _REWRITE_STRICT_RETRY,
        # article_writing
        _WRITING_DEFAULT,
        _WRITING_POSTCARD,
        _WRITING_SYSTEM_DEFAULT,
        _WRITING_SYSTEM_DEVTOOLS,
        _WRITING_SYSTEM_PARAGRAPH,
        _WRITING_SYSTEM_POSTCARD,
        _WRITING_DEVTOOLS_INSTRUCTIONS,
        _WRITING_PARAGRAPH_INSTRUCTIONS,
        # image_prompts
        _IMAGE_WRITER_HINT_DEFAULT,
        _IMAGE_WRITER_HINT_POSTCARD,
        _IMAGE_WRITER_HINT_PARAGRAPH,
        _IMAGE_LOGO_EDIT_TEMPLATE,
        _IMAGE_COVER_PROMPT,
        _IMAGE_COVER_PROMPT_POSTCARD,
        # image_negatives
        _NEGATIVE_QWEN_NO_TEXT,
        _NEGATIVE_QWEN_NEWS,
        _NEGATIVE_QWEN_LOGO_EDIT,
    ]
}

CATEGORY_LABELS: dict[str, str] = {
    "classification": "Классификация",
    "topic_selection": "Отбор новостей",
    "topic_ideation": "Идеация тем",
    "rewriting": "Рерайт",
    "article_writing": "Написание статей",
    "image_prompts": "Обложки",
    "image_negatives": "Негативные промпты",
}

CATEGORY_ORDER: list[str] = [
    "classification",
    "topic_selection",
    "topic_ideation",
    "rewriting",
    "article_writing",
    "image_prompts",
    "image_negatives",
]
