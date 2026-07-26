"""Генерация темы для автономной статьи."""

import json
import re
from dataclasses import dataclass
from datetime import date

from loguru import logger

from app.core.config import get_settings
from app.domain.article import ArticleTopicPlan
from app.domain.postcard_calendar import today_holiday
from app.domain.topic_dedup import is_topic_too_similar
from app.infrastructure.ai.deepseek_client import DeepSeekClient
from app.infrastructure.ai.devtools_teaser_formatter import is_devtools_article_channel
from app.infrastructure.ai.paragraph_teaser_formatter import is_paragraph_article_channel
from app.infrastructure.ai.postcard_teaser_formatter import is_postcard_article_channel
from app.infrastructure.models.channel import Channel
from app.utils.safe_format import safe_format

_MAX_IDEATION_ATTEMPTS = 5


@dataclass(frozen=True)
class IdeationPrompts:
    """Промпты идеации из панели промптов (prompt_templates: ideation.*)."""

    default_template: str
    postcard_template: str
    system_default: str
    system_postcard: str
    system_paragraph: str
    devtools_extra: str
    devtools_with_repos: str
    devtools_no_repos: str
    paragraph_extra: str


class TopicIdeationService:
    """Придумывает тему и поисковые запросы для статьи.

    Все тексты промптов приходят из БД через ``IdeationPrompts`` —
    модуль не содержит захардкоженных промптов.
    """

    def __init__(
        self,
        prompts: IdeationPrompts,
        client: DeepSeekClient | None = None,
    ) -> None:
        self._client = client or DeepSeekClient()
        self._prompts = prompts

    async def plan_topic(
        self,
        channel: Channel,
        recent_topics: list[str],
        candidate_repos: list[str] | None = None,
    ) -> ArticleTopicPlan:
        """Генерирует план темы статьи с проверкой на повторы.

        Args:
            channel: канал публикации.
            recent_topics: недавние темы для антиповтора.
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
        candidate_repos: list[str] | None = None,
    ) -> ArticleTopicPlan:
        """Один запрос к модели за темой статьи.

        Args:
            channel: канал публикации.
            blocked_topics: темы, которые нельзя предлагать.
            candidate_repos: живой список трендовых репозиториев для выбора.

        Returns:
            ArticleTopicPlan: распознанный план.

        Raises:
            RuntimeError: при ошибке парсинга ответа.
        """
        niche = (channel.style_prompt or "познавательные статьи").strip()
        recent = _format_recent_topics(blocked_topics)
        prompt = safe_format(
            self._prompts.default_template,
            channel_name=channel.name,
            channel_niche=niche,
            recent_topics=recent,
        )
        if is_postcard_article_channel(channel.name):
            today = date.today()
            prompt = safe_format(
                self._prompts.postcard_template,
                channel_name=channel.name,
                channel_niche=niche,
                recent_topics=recent,
                current_date=today.strftime("%d.%m.%Y"),
                today_holiday=today_holiday(today),
            )
        elif is_devtools_article_channel(channel.topic, channel.name):
            prompt = f"{prompt}\n\n{self._devtools_extra(candidate_repos)}"
        elif is_paragraph_article_channel(channel.name):
            prompt = f"{prompt}\n\n{self._prompts.paragraph_extra}"

        settings = get_settings()
        result = await self._client.chat_completion(
            system_prompt=self._system_prompt(channel),
            user_prompt=prompt,
            max_tokens=4000,
            temperature=0.85,
            model=settings.deepseek_model,
            json_mode=True,
        )
        parsed = self._parse_response(result)
        if parsed is None:
            logger.warning("Topic ideation parse failed", preview=result[:400])
            msg = "Не удалось распознать тему статьи от модели"
            raise RuntimeError(msg)
        return parsed

    def _devtools_extra(self, candidate_repos: list[str] | None) -> str:
        """Собирает блок инструкций devtools: общие правила + ветка по трендам.

        Args:
            candidate_repos: живой список трендовых репозиториев или None.

        Returns:
            str: блок инструкций для промпта идеации.
        """
        base = self._prompts.devtools_extra
        if candidate_repos:
            with_repos = safe_format(
                self._prompts.devtools_with_repos,
                repos_block=_format_repo_lines(candidate_repos),
            )
            return f"{base}\n\n{with_repos}"
        return f"{base}\n{self._prompts.devtools_no_repos}"

    def _system_prompt(self, channel: Channel) -> str:
        """Выбирает системный промпт по типу канала.

        Args:
            channel: канал публикации.

        Returns:
            str: системная инструкция из панели промптов.
        """
        if is_postcard_article_channel(channel.name):
            return self._prompts.system_postcard
        if is_paragraph_article_channel(channel.name):
            return self._prompts.system_paragraph
        return self._prompts.system_default

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


def _format_repo_lines(candidate_repos: list[str]) -> str:
    """Форматирует живой список репозиториев для подстановки в {repos_block}.

    Только форматирование данных GitHub Trending — текст инструкций вокруг
    списка редактируется в панели промптов (ideation.devtools_with_repos).

    Args:
        candidate_repos: строки-описания репозиториев.

    Returns:
        str: список в виде «- строка» через перевод строки.
    """
    return "\n".join(f"- {line}" for line in candidate_repos)
