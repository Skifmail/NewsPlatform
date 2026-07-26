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

_REWRITE_MAX_TOKENS = 4096


class ContentRewriter:
    """Рерайтер контента под стиль канала.

    Промпты (шаблон, системный, суффикс повтора) приходят из панели промптов
    (таблица prompt_templates) — модуль не содержит захардкоженных текстов.
    """

    def __init__(
        self,
        *,
        default_template: str,
        system_prompt: str,
        retry_suffix: str,
        client: DeepSeekClient | None = None,
    ) -> None:
        self._client = client or DeepSeekClient()
        self._default_template = default_template
        self._system_prompt = system_prompt
        self._retry_suffix = retry_suffix

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
            return self._default_template, custom
        return self._default_template, "Нейтральный информативный стиль."

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
            system_prompt=self._system_prompt,
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
                system_prompt=self._system_prompt,
                user_prompt=f"{prompt}{self._retry_suffix}",
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
