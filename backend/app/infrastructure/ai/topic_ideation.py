"""Генерация темы для автономной статьи."""

import json
import re

from loguru import logger

from app.core.config import get_settings
from app.domain.article import ArticleTopicPlan
from app.domain.topic_dedup import is_topic_too_similar
from app.infrastructure.ai.deepseek_client import DeepSeekClient
from app.infrastructure.ai.devtools_teaser_formatter import is_devtools_article_channel
from app.infrastructure.ai.paragraph_teaser_formatter import is_paragraph_article_channel
from app.infrastructure.models.channel import Channel

_MAX_IDEATION_ATTEMPTS = 5

_DEFAULT_IDEATION_PROMPT = """Ты — редактор познавательного Telegram-канала «{channel_name}».
Ниша канала: {channel_niche}

Недавние темы и заголовки (СТРОГО ЗАПРЕЩЕНО повторять и близкие по смыслу):
{recent_topics}

Правила выбора темы:
- Одна конкретная концепция = одна статья. Нельзя перефразировать недавнюю тему другими словами.
- Если недавно был «эффект плацебо» — запрещены сахарная таблетка, сила внушения, самовнушение и т.п.
- Если недавно было «дежавю» — запрещены ложные воспоминания, déjà vu, «уже здесь были».
- Чередуй области знаний: космос, история, биология, физика, технологии, культура, экономика, язык, археология.
- Не выбирай подряд несколько тем из одной области (психология мозга, оптические иллюзии и т.д.).
- Тема должна быть интересной широкой аудитории, с потенциалом для фактов из интернета.

Придумай ОДНУ свежую познавательную тему для длинной статьи на русском.

Ответь строго JSON одной строкой:
{{"topic": "краткое название темы", "angle": "угол подачи в 1-2 предложения", "search_queries": ["запрос 1", "запрос 2", "запрос 3"]}}"""


class TopicIdeationService:
    """Придумывает тему и поисковые запросы для статьи."""

    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self._client = client or DeepSeekClient()

    async def plan_topic(
        self,
        channel: Channel,
        recent_topics: list[str],
        prompt_template: str,
        candidate_repos: list[str] | None = None,
    ) -> ArticleTopicPlan:
        """Генерирует план темы статьи с проверкой на повторы.

        Args:
            channel: канал публикации.
            recent_topics: недавние темы для антиповтора.
            prompt_template: шаблон промпта из settings.
            candidate_repos: живой список трендовых репозиториев (GitHub
                Trending) для devtools-канала. Если задан — модель выбирает
                тему из него, а не выдумывает из памяти.

        Returns:
            ArticleTopicPlan: тема, угол и запросы для поиска.

        Raises:
            RuntimeError: если модель вернула невалидный JSON или не нашла уникальную тему.
        """
        blocked = list(recent_topics)
        last_plan: ArticleTopicPlan | None = None
        # Для devtools/trending-каналов дедуп идёт по РЕПОЗИТОРИЮ (кандидаты
        # уже отфильтрованы от опубликованных по github-ссылке). Словесная
        # похожесть заголовков тут ложно режет РАЗНЫЕ репозитории с общими
        # тех-словами (design/ai/альтернатива) — поэтому её не применяем.
        repo_mode = bool(candidate_repos)

        for attempt in range(1, _MAX_IDEATION_ATTEMPTS + 1):
            plan = await self._request_topic(
                channel,
                blocked_topics=blocked,
                prompt_template=prompt_template,
                candidate_repos=candidate_repos,
            )
            last_plan = plan
            if repo_mode:
                return plan
            if not is_topic_too_similar(plan.topic, blocked) and not is_topic_too_similar(
                f"{plan.topic} {plan.angle}", blocked
            ):
                if attempt > 1:
                    logger.info(
                        "Topic ideation succeeded after retry",
                        channel_id=channel.id,
                        topic=plan.topic,
                        attempt=attempt,
                    )
                return plan

            logger.warning(
                "Topic ideation rejected as duplicate",
                channel_id=channel.id,
                topic=plan.topic,
                attempt=attempt,
            )
            blocked.append(plan.topic)
            if plan.angle.strip():
                blocked.append(f"{plan.topic} {plan.angle}")

        if last_plan is not None:
            msg = (
                f"Не удалось подобрать уникальную тему после {_MAX_IDEATION_ATTEMPTS} "
                f"попыток (последняя: {last_plan.topic})"
            )
            raise RuntimeError(msg)
        msg = "Не удалось распознать тему статьи от модели"
        raise RuntimeError(msg)

    async def _request_topic(
        self,
        channel: Channel,
        *,
        blocked_topics: list[str],
        prompt_template: str,
        candidate_repos: list[str] | None = None,
    ) -> ArticleTopicPlan:
        """Один запрос к модели за темой статьи.

        Args:
            channel: канал публикации.
            blocked_topics: темы, которые нельзя предлагать.
            prompt_template: шаблон промпта из settings.
            candidate_repos: живой список трендовых репозиториев для выбора.

        Returns:
            ArticleTopicPlan: распознанный план.

        Raises:
            RuntimeError: при ошибке парсинга ответа.
        """
        niche = (channel.style_prompt or "познавательные статьи").strip()
        recent = _format_recent_topics(blocked_topics)
        template = prompt_template.strip() or _DEFAULT_IDEATION_PROMPT
        prompt = template.format(
            channel_name=channel.name,
            channel_niche=niche,
            recent_topics=recent,
        )
        if is_devtools_article_channel(channel.topic, channel.name):
            prompt = f"{prompt}\n\n{_devtools_ideation_extra(candidate_repos)}"
        elif is_paragraph_article_channel(channel.name):
            prompt = f"{prompt}\n\n{_paragraph_ideation_extra()}"

        settings = get_settings()
        result = await self._client.chat_completion(
            system_prompt=_system_prompt(channel),
            user_prompt=prompt,
            max_tokens=512,
            temperature=0.85,
            model=settings.deepseek_fast_model,
            json_mode=True,
        )
        parsed = self._parse_response(result)
        if parsed is None:
            logger.warning("Topic ideation parse failed", preview=result[:400])
            msg = "Не удалось распознать тему статьи от модели"
            raise RuntimeError(msg)
        return parsed

    @staticmethod
    def _parse_response(result: str) -> ArticleTopicPlan | None:
        """Извлекает план темы из ответа модели.

        Args:
            result: сырой ответ.

        Returns:
            ArticleTopicPlan | None: распознанный план.
        """
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{[^{}]*\"topic\"[^{}]*\}", cleaned, re.DOTALL)
            if not match:
                return None
            try:
                data = json.loads(match.group(0))
            except json.JSONDecodeError:
                return None
        if not isinstance(data, dict):
            return None
        topic = str(data.get("topic", "")).strip()
        angle = str(data.get("angle", "")).strip()
        queries_raw = data.get("search_queries") or []
        if not topic or not isinstance(queries_raw, list):
            return None
        queries = [str(q).strip() for q in queries_raw if str(q).strip()][:3]
        if not queries:
            queries = [topic, f"{topic} facts", f"{topic} research"]
        return ArticleTopicPlan(topic=topic, angle=angle, search_queries=queries)


def _format_recent_topics(topics: list[str]) -> str:
    """Форматирует список недавних тем для промпта.

    Args:
        topics: темы от новых к старым.

    Returns:
        str: нумерованный список или «нет».
    """
    if not topics:
        return "нет"
    lines = [f"{index}. {topic}" for index, topic in enumerate(topics[:25], start=1)]
    return "\n".join(lines)


def _system_prompt(channel: Channel) -> str:
    """Возвращает системный промпт для выбора темы.

    Args:
        channel: канал публикации.

    Returns:
        str: системная инструкция.
    """
    base = (
        "Ты придумываешь темы для познавательных статей. "
        "Никогда не повторяй и не перефразируй недавние темы. "
        "Ответь только JSON с полями topic, angle, search_queries."
    )
    if is_paragraph_article_channel(channel.name):
        return (
            f"{base} "
            "Для канала «Параграф» чередуй разные области знаний — "
            "не предлагай подряд психологию мозга и когнитивные эффекты."
        )
    return base


def _devtools_ideation_extra(candidate_repos: list[str] | None) -> str:
    """Инструкции идеации для канала GitHub-находок.

    Args:
        candidate_repos: живой список трендовых репозиториев (строки-описания).
            Если задан — модель выбирает из него; иначе выбирает из своих знаний.

    Returns:
        str: блок инструкций для промпта.
    """
    base = (
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
    )
    if candidate_repos:
        repos_block = "\n".join(f"- {line}" for line in candidate_repos)
        return (
            f"{base}\n\n"
            "Ниже — ЖИВОЙ список трендовых репозиториев GitHub прямо сейчас. "
            "Выбери РОВНО ОДИН из этого списка (не выдумывай свой), тот, что "
            "будет интереснее всего аудитории и ещё не выходил в канале.\n"
            f"{repos_block}\n\n"
            'Поле topic — «owner/repo: суть», в angle укажи, чем цепляет. '
            "В search_queries укажи запросы именно про выбранный репозиторий: "
            '"<repo> github", "<repo> features", "<repo> alternative".'
        )
    return (
        f"{base}\n"
        "В search_queries обязательно добавь запросы, подтверждающие "
        "актуальность и популярность, например: "
        '"<repo> github stars", "<repo> github trending 2026", '
        '"<repo> open source alternative".'
    )


def _paragraph_ideation_extra() -> str:
    """Дополнительные правила идеации для канала «Параграф».

    Returns:
        str: блок инструкций.
    """
    return """Канал «Параграф» — познавательные статьи для широкой аудитории.

Обязательно:
- Тема из ДРУГОЙ области, чем последние 3–5 статей в списке выше.
- Запрещены синонимы и перефразировки недавних тем (плацебо ≠ сахарная таблетка ≠ сила внушения).
- Хорошие области для разнообразия: космос, древний мир, животные, физика, язык, архитектура,
  экономические парадоксы, редкие профессии, географические аномалии, изобретения.
- Плохо: подряд несколько статей про мозг, память, иллюзии, плацебо, дежавю, сны.

Баланс (смотри список недавних тем выше):
- ГЕОГРАФИЯ: не бери страну/регион, уже мелькавшие в последних темах. Особенно
  не зацикливайся на одной стране (например Япония) — если она уже была недавно,
  выбери другую часть света или тему без гео-привязки.
- СУБЪЕКТ: не бери того же героя (животное, здание, явление, изобретение), что
  уже был недавно, даже под другим названием (шмель ≠ пчела-нарушитель;
  пирамиды Гизы ≠ пирамиды Амазонии).
- ЗАГОЛОВОК: разнообразь зачин. Если последние 2–3 заголовка начинались с
  «Почему» — начни иначе (факт-парадокс, «Как…», число, утверждение, вопрос без
  «почему»). Не более чем каждый третий заголовок может начинаться с «Почему»."""
