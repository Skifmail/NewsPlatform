"""Написание длинных познавательных статей."""

import json
import re

from loguru import logger

from app.core.config import get_settings
from app.domain.article import ArticleDraft
from app.infrastructure.ai.deepseek_client import DeepSeekClient
from app.infrastructure.ai.devtools_teaser_formatter import (
    build_devtools_teaser,
    devtools_writing_instructions,
    extract_github_url,
    is_devtools_article_channel,
)
from app.infrastructure.ai.paragraph_teaser_formatter import (
    build_paragraph_teaser,
    is_paragraph_article_channel,
    paragraph_writing_instructions,
)
from app.infrastructure.ai.image_prompt_builder import ImagePromptBuilder
from app.infrastructure.models.channel import Channel
from app.utils.text_format import normalize_telegram_html
from app.utils.article_body_sanitize import sanitize_article_body_html
from app.utils.safe_format import safe_format

# Лимит вывода deepseek-chat ≈8192 токена; длинный JSON с HTML не влезает в 12000 символов.
_ARTICLE_OUTPUT_CHAR_CAP = 7500
_ARTICLE_MAX_TOKENS = 32000

# Завершающая предложение пунктуация — чтобы не обрывать статью на полуслове.
_SENTENCE_ENDINGS = ".!?…»"


def _trim_to_last_sentence(text: str) -> str:
    """Обрезает текст до последнего завершённого предложения.

    Применяется, когда тело обрезано по max_tokens или по символьному лимиту —
    чтобы статья заканчивалась законченной мыслью, а не «…» на полуслове.

    Args:
        text: тело статьи (HTML).

    Returns:
        str: тело, оканчивающееся полным предложением.
    """
    stripped = text.rstrip()
    if not stripped or stripped[-1] in _SENTENCE_ENDINGS:
        return stripped
    best = max((stripped.rfind(ch) for ch in _SENTENCE_ENDINGS), default=-1)
    if best == -1:
        return stripped
    tail = stripped[best + 1 :]
    match = re.match(r'["»)]*(?:</[a-zA-Z0-9]+>)*', tail)
    end = best + 1 + (match.end() if match else 0)
    return stripped[:end].rstrip()

_DEFAULT_WRITING_PROMPT = """Ты — автор познавательных статей для Telegram-канала «{channel_name}».
Стиль канала: {channel_niche}

Напиши статью на русском по теме «{topic}» ({angle}).
Используй ТОЛЬКО факты из блока «Исследование» ниже. Не выдумывай цитаты и цифры.

Структура body_html (без служебных меток «Крючок», «Вывод», «Лид», «Источники» — только содержательные подзаголовки):
1) Лид — 2-3 предложения (без заголовка «Лид»)
2) 3-5 разделов с подзаголовками <b>...</b> по теме
3) Заключительный абзац — 2-3 предложения (без заголовка «Вывод»)
4) Ссылки на источники — список <a href="...">название</a> (без заголовка «Источники»)

HTML в body_html: только теги b, i, a, blockquote. Без <p>. Абзацы — через \\n\\n внутри строки JSON.
Объём body_html: {min_length}–{max_length} символов.
Teaser (анонс для Telegram): до {teaser_max_length} символов, интригует, без спойлеров всей статьи.

Правила обложки (поле image_prompt, только английский):
{image_guidelines}

image_prompt — 1–2 предложения: ОДНА конкретная визуальная метафора инструмента или темы.
Запрещено: нейросети, матричный дождь, голограммы, множество окон, нечитаемый код, любой текст на картинке.

Ответь строго одним JSON-объектом с ключами title, teaser, body_html, image_prompt.

Исследование:
{research_context}"""

_SYSTEM_PROMPT = (
    "Ты автор познавательных статей на русском. "
    "Пиши увлекательно, но строго по фактам из исследования. "
    "Ответь только валидным JSON с ключами title, teaser, body_html, image_prompt."
)

_DEVTOOLS_SYSTEM_PROMPT = (
    "Ты автор карточек GitHub-находок на русском. "
    "Строго по фактам из исследования — не выдумывай stars, forks и язык. "
    "Крючок (hook) — разный заход в каждой карточке; не начинай с «Устали от» и похожих шаблонов. "
    "Ответь только валидным JSON с ключами: title, teaser, body_html, image_prompt, "
    "project_name, repo_url, language, stars, forks, hook, features, insight."
)

_PARAGRAPH_SYSTEM_PROMPT = (
    "Ты автор познавательных статей на русском для канала «Параграф». "
    "Пиши увлекательно, но строго по фактам из исследования. "
    "Ответь только валидным JSON с ключами: title, teaser, body_html, image_prompt, "
    "hook, quote, closing."
)


class ArticleWriter:
    """Генерирует длинную статью по результатам исследования."""

    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self._client = client or DeepSeekClient()

    async def write(
        self,
        channel: Channel,
        *,
        topic: str,
        angle: str,
        research_context: str,
        prompt_template: str,
        body_max_length: int,
        teaser_max_length: int,
        recent_hooks: list[str] | None = None,
    ) -> ArticleDraft:
        """Пишет статью по собранному контексту.

        Args:
            channel: канал публикации.
            topic: тема статьи.
            angle: угол подачи.
            research_context: текст исследования.
            prompt_template: шаблон промпта.
            body_max_length: лимит тела статьи.
            teaser_max_length: лимит анонса.
            recent_hooks: недавние крючки devtools-канала (антиповтор).

        Returns:
            ArticleDraft: черновик статьи.

        Raises:
            RuntimeError: при ошибке парсинга ответа.
        """
        effective_body_max = min(body_max_length, _ARTICLE_OUTPUT_CHAR_CAP)
        if effective_body_max < body_max_length:
            logger.info(
                "Article body cap applied for model output",
                requested=body_max_length,
                effective=effective_body_max,
            )

        draft = await self._generate_draft(
            channel=channel,
            topic=topic,
            angle=angle,
            research_context=research_context,
            prompt_template=prompt_template,
            body_max_length=effective_body_max,
            teaser_max_length=teaser_max_length,
            recent_hooks=recent_hooks,
        )
        if draft is not None:
            return draft

        # Повтор с укороченным телом — если JSON обрезан по max_tokens.
        shorter_max = max(3500, effective_body_max // 2)
        logger.warning(
            "Article parse retry with shorter body",
            first_cap=effective_body_max,
            retry_cap=shorter_max,
        )
        draft = await self._generate_draft(
            channel=channel,
            topic=topic,
            angle=angle,
            research_context=research_context,
            prompt_template=prompt_template,
            body_max_length=shorter_max,
            teaser_max_length=teaser_max_length,
            recent_hooks=recent_hooks,
        )
        if draft is None:
            msg = "Не удалось распознать статью от модели"
            raise RuntimeError(msg)
        return draft

    async def _generate_draft(
        self,
        *,
        channel: Channel,
        topic: str,
        angle: str,
        research_context: str,
        prompt_template: str,
        body_max_length: int,
        teaser_max_length: int,
        recent_hooks: list[str] | None = None,
    ) -> ArticleDraft | None:
        """Один запрос к модели и парсинг ответа.

        Args:
            channel: канал публикации.
            topic: тема.
            angle: угол.
            research_context: контекст исследования.
            prompt_template: шаблон промпта.
            body_max_length: лимит тела.
            teaser_max_length: лимит анонса.
            recent_hooks: недавние крючки devtools-канала.

        Returns:
            ArticleDraft | None: черновик или None при ошибке парсинга.
        """
        niche = (channel.style_prompt or "познавательные статьи").strip()
        image_guidelines = ImagePromptBuilder.writer_image_guidelines(channel)
        template = prompt_template.strip() or _DEFAULT_WRITING_PROMPT
        min_length = max(2500, body_max_length // 2)
        prompt = safe_format(
            template,
            channel_name=channel.name,
            channel_niche=niche,
            topic=topic,
            angle=angle or topic,
            min_length=min_length,
            max_length=body_max_length,
            teaser_max_length=teaser_max_length,
            image_guidelines=image_guidelines,
            research_context=research_context,
        )
        devtools = is_devtools_article_channel(channel.topic, channel.name)
        paragraph = is_paragraph_article_channel(channel.name)
        if devtools:
            prompt = (
                f"{prompt}\n\n"
                f"{devtools_writing_instructions(teaser_max_length, recent_hooks=recent_hooks)}"
            )
        elif paragraph:
            prompt = f"{prompt}\n\n{paragraph_writing_instructions(teaser_max_length)}"
        if devtools:
            system_prompt = _DEVTOOLS_SYSTEM_PROMPT
        elif paragraph:
            system_prompt = _PARAGRAPH_SYSTEM_PROMPT
        else:
            system_prompt = _SYSTEM_PROMPT
        settings = get_settings()
        result, finish_reason = await self._client.chat_completion_with_meta(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=_ARTICLE_MAX_TOKENS,
            temperature=0.5,
            model=settings.deepseek_model,
            json_mode=True,
        )
        if finish_reason == "length":
            logger.warning(
                "Article truncated by max_tokens — обрежем по последнему предложению",
                chars=len(result),
                max_tokens=_ARTICLE_MAX_TOKENS,
            )
        draft = self._parse_response(
            result,
            body_max_length,
            teaser_max_length,
            channel=channel,
            research_context=research_context,
            truncated=finish_reason == "length",
        )
        if draft is None:
            logger.warning(
                "Article write parse failed",
                preview=result[:800],
                response_chars=len(result),
            )
        return draft

    @staticmethod
    def _parse_response(
        result: str,
        body_max_length: int,
        teaser_max_length: int,
        *,
        channel: Channel | None = None,
        research_context: str = "",
        truncated: bool = False,
    ) -> ArticleDraft | None:
        """Парсит JSON-ответ модели.

        Args:
            result: сырой ответ.
            body_max_length: лимит тела.
            teaser_max_length: лимит анонса.
            channel: канал публикации (для формата devtools).
            research_context: текст исследования (fallback repo_url).

        Returns:
            ArticleDraft | None: черновик или None.
        """
        data = ArticleWriter._load_json_object(result)
        if not isinstance(data, dict):
            data = ArticleWriter._extract_fields_fallback(result)
        if not isinstance(data, dict):
            return None

        title = str(data.get("title", "")).strip()
        teaser = str(data.get("teaser", "")).strip()
        body = normalize_telegram_html(str(data.get("body_html", "")).strip())
        image_prompt = str(data.get("image_prompt", "")).strip()
        if not title or not body:
            return None
        if truncated:
            body = _trim_to_last_sentence(body)
        if len(body) > body_max_length:
            body = _trim_to_last_sentence(body[:body_max_length])
        if channel and is_devtools_article_channel(channel.topic, channel.name):
            teaser = build_devtools_teaser(
                data,
                teaser_max_length=teaser_max_length,
                research_context=research_context,
            )
        elif channel and is_paragraph_article_channel(channel.name):
            teaser = build_paragraph_teaser(
                data,
                teaser_max_length=teaser_max_length,
            )
        elif len(teaser) > teaser_max_length:
            teaser = f"{teaser[: teaser_max_length - 1].rstrip()}…"
        teaser = normalize_telegram_html(teaser)
        body = sanitize_article_body_html(body, teaser_html=teaser)
        if not image_prompt:
            image_prompt = f"Editorial illustration about: {title[:200]}"
        repo_url = str(data.get("repo_url") or "").strip()
        if not repo_url and research_context:
            repo_url = extract_github_url(research_context)
        # Для github-находок ссылка на репозиторий обязана быть в теле статьи,
        # а не только в тизере — модель её часто не добавляет.
        if (
            repo_url
            and channel is not None
            and is_devtools_article_channel(channel.topic, channel.name)
            and "github.com" not in body.lower()
        ):
            body = (
                f'{body}\n\n<b>🔗 Репозиторий:</b> '
                f'<a href="{repo_url}">{repo_url}</a>'
            )
        return ArticleDraft(
            title=title,
            teaser=teaser,
            body_html=body,
            image_prompt=image_prompt,
            repo_url=repo_url or None,
        )

    @staticmethod
    def _load_json_object(result: str) -> dict[str, object] | None:
        """Пытается распарсить JSON-объект из ответа модели.

        Args:
            result: сырой ответ.

        Returns:
            dict[str, object] | None: объект или None.
        """
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            pass

        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            fragment = cleaned[start : end + 1]
            try:
                data = json.loads(fragment)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                pass
        return None

    @staticmethod
    def _extract_fields_fallback(text: str) -> dict[str, str] | None:
        """Извлекает поля статьи из повреждённого JSON.

        Args:
            text: сырой ответ модели.

        Returns:
            dict[str, str] | None: поля или None.
        """
        title = ArticleWriter._extract_quoted_field(text, "title")
        teaser = ArticleWriter._extract_quoted_field(text, "teaser")
        body = ArticleWriter._extract_quoted_field(text, "body_html")
        image_prompt = ArticleWriter._extract_quoted_field(text, "image_prompt")
        if not title or not body:
            return None
        return {
            "title": title,
            "teaser": teaser or "",
            "body_html": body.replace("\\n", "\n"),
            "image_prompt": image_prompt or "",
        }

    @staticmethod
    def _extract_quoted_field(text: str, field: str) -> str | None:
        """Извлекает строковое поле из JSON-подобного текста.

        Args:
            text: исходный текст.
            field: имя поля.

        Returns:
            str | None: значение или None.
        """
        pattern = rf'"{re.escape(field)}"\s*:\s*"((?:[^"\\]|\\.)*)"'
        match = re.search(pattern, text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(f'"{match.group(1)}"')
        except json.JSONDecodeError:
            return match.group(1).replace("\\n", "\n").replace('\\"', '"')
