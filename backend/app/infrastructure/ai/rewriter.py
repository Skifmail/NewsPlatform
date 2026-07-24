"""Рерайт новостей через DeepSeek."""

from loguru import logger

from app.core.config import get_settings
from app.infrastructure.ai.deepseek_client import DeepSeekClient
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.raw_post import RawPost
from app.utils.rewrite_output import is_publishable_rewrite, sanitize_rewrite_output
from app.utils.safe_format import safe_format
from app.utils.text_format import (
    MAX_REWRITE_LENGTH,
    clamp_rewrite_length,
    ensure_source_link,
    normalize_telegram_html,
)

from app.domain.topics import TOPIC_LABELS as _TOPIC_LABELS

# Дефолт, если в канале промпт не задан. Полный шаблон можно вставить в «Каналы → Промпт рерайта».
DEFAULT_REWRITE_TEMPLATE = """Ты — редактор Telegram-канала "{channel_name}" с тематикой "{topic_label}".
Дополнительный стиль: {style_prompt}

Перепиши новость для публикации в канале. Объём: до {max_length} символов.

СТРУКТУРА (строго, каждый блок — отдельный фрагмент, между блоками пустая строка):

1) Заголовок-выжимка:
<b>Главная мысль новости одной фразой</b>

2) Лид — 2-3 предложения сути:
Кратко что произошло. Можно 1 уместный эмодзи 🇷🇺 📱 🚗

3) Цитата — ОТДЕЛЬНЫЙ блок:
<blockquote expandable>«Прямая цитата или ключевая фраза из новости» — имя/должность</blockquote>
Если прямой цитаты нет — вынеси главный тезис в blockquote.

4) Контекст — 2-4 предложения (фон, цифры, последствия).

5) Вовлечение — вопрос или призыв к обсуждению ... 🤔

6) Ссылка на источник (если URL задан):
<a href="{source_url}">Читать в источнике →</a>

Правила оформления:
- Только теги: b, blockquote, a, i (i — только внутри blockquote при необходимости)
- ЗАПРЕЩЕНО: тег <p> (Telegram Bot API его не принимает)
- Между блоками 1-2 — пустая строка, не <br> внутри одного абзаца
- Без вводных «Итак», «Таким образом»
- Без хэштегов (добавятся при публикации)
- Сохрани факты, перепиши своими словами под аудиторию канала
- Отвечай ТОЛЬКО HTML-текстом поста, без пояснений

Ссылка на источник: {source_url_display}

Оригинальная новость:
{original_text}"""

_REWRITER_SYSTEM_PROMPT = (
    "Ты редактор Telegram-канала. Пиши блочно: абзацы через пустую строку, "
    "без тега <p>. Цитаты только в <blockquote expandable>. "
    "Стиль — как у крупных новостных каналов: заголовок, лид, цитата, контекст, вопрос. "
    "Отвечай ТОЛЬКО готовым HTML поста. Никогда не выводи черновики, анализ фактов "
    "или пояснения к заданию."
)

_STRICT_RETRY_SUFFIX = (
    "\n\nКРИТИЧНО: в ответе только финальный HTML поста для Telegram. "
    "Без анализа, без списков фактов, без markdown, без рассуждений."
)

_REWRITE_MAX_TOKENS = 4096


class ContentRewriter:
    """Рерайтер контента под стиль канала."""

    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self._client = client or DeepSeekClient()

    def _resolve_template(self, channel: Channel) -> tuple[str, str]:
        """Выбирает шаблон промпта и доп. стиль канала.

        Если в ``style_prompt`` есть ``{original_text}`` — это полный пользовательский
        шаблон из раздела «Каналы». Иначе ``style_prompt`` — только описание стиля.

        Args:
            channel: канал публикации.

        Returns:
            tuple[str, str]: (шаблон промпта, значение для {style_prompt}).
        """
        custom = (channel.style_prompt or "").strip()
        if custom and "{original_text}" in custom:
            return custom, ""
        if custom:
            return DEFAULT_REWRITE_TEMPLATE, custom
        return DEFAULT_REWRITE_TEMPLATE, "Нейтральный информативный стиль."

    async def rewrite(self, raw_post: RawPost, channel: Channel) -> str:
        """Переписывает пост под канал.

        Args:
            raw_post: сырой пост.
            channel: канал с style_prompt (полный шаблон или описание стиля).

        Returns:
            str: переписанный текст с HTML-разметкой и ссылкой на источник.

        Raises:
            RuntimeError: если модель вернула непубликабельный текст.
        """
        original = raw_post.content
        if raw_post.title:
            original = f"{raw_post.title}\n\n{raw_post.content}"

        source_url = (raw_post.url or "").strip()
        topic_label = _TOPIC_LABELS.get(channel.topic, channel.topic)
        template, style_notes = self._resolve_template(channel)

        prompt = safe_format(
            template,
            channel_name=channel.name,
            topic=channel.topic,
            topic_label=topic_label,
            style_prompt=style_notes,
            max_length=MAX_REWRITE_LENGTH,
            source_url=source_url or "#",
            source_url_display=source_url or "нет",
            original_text=original[:4000],
        )
        settings = get_settings()
        model = settings.deepseek_fast_model

        raw, finish_reason = await self._client.chat_completion_with_meta(
            system_prompt=_REWRITER_SYSTEM_PROMPT,
            user_prompt=prompt,
            max_tokens=_REWRITE_MAX_TOKENS,
            model=model,
            temperature=0.5,
        )
        result = self._finalize_rewrite(raw, source_url)

        needs_retry = finish_reason == "length" or not is_publishable_rewrite(result)
        if needs_retry:
            logger.warning(
                "Rewrite invalid or truncated, retrying",
                channel_id=channel.id,
                raw_post_id=raw_post.id,
                finish_reason=finish_reason,
                preview=raw[:200],
            )
            raw_retry, finish_retry = await self._client.chat_completion_with_meta(
                system_prompt=_REWRITER_SYSTEM_PROMPT,
                user_prompt=f"{prompt}{_STRICT_RETRY_SUFFIX}",
                max_tokens=_REWRITE_MAX_TOKENS,
                model=model,
                temperature=0.35,
            )
            result = self._finalize_rewrite(raw_retry, source_url)
            if not is_publishable_rewrite(result) or finish_retry == "length":
                msg = "Модель вернула непубликабельный рерайт"
                raise RuntimeError(msg)

        return result

    @staticmethod
    def _finalize_rewrite(raw: str, source_url: str) -> str:
        """Нормализует сырой ответ модели в текст поста.

        Args:
            raw: ответ API.
            source_url: URL источника.

        Returns:
            str: готовый HTML для Telegram.

        Raises:
            ValueError: если ответ — рассуждения модели, а не пост.
        """
        cleaned = sanitize_rewrite_output(raw)
        normalized = normalize_telegram_html(cleaned)
        with_link = ensure_source_link(normalized, source_url or None)
        return clamp_rewrite_length(with_link, MAX_REWRITE_LENGTH)
