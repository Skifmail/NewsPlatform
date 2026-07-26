"""Классификация тематики через DeepSeek."""

from loguru import logger

from app.core.config import get_settings
from app.domain.enums import Topic
from app.infrastructure.ai.deepseek_client import DeepSeekClient


class TopicClassifier:
    """Определяет тематику новости."""

    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self._client = client or DeepSeekClient()

    async def classify(
        self,
        text: str,
        prompt_template: str,
        system_prompt: str,
        fallback_topic: str | None = None,
    ) -> str:
        """Классифицирует текст.

        Args:
            text: текст новости.
            prompt_template: шаблон с {text} (из панели промптов).
            system_prompt: системный промпт классификатора (из панели промптов).
            fallback_topic: тема источника, если модель вернула пустой ответ.

        Returns:
            str: it | auto | russia | sport.
        """
        prompt = prompt_template.replace("{text}", text[:3000])
        settings = get_settings()
        result = await self._client.chat_completion(
            system_prompt=system_prompt,
            user_prompt=prompt,
            max_tokens=2000,
            temperature=0.0,
            model=settings.deepseek_fast_model,
        )
        return self._parse_topic(result, fallback_topic)

    @staticmethod
    def _parse_topic(result: str, fallback_topic: str | None) -> str:
        """Извлекает тему из ответа модели.

        Args:
            result: сырой ответ API.
            fallback_topic: запасная тема (из источника).

        Returns:
            str: it | auto | russia | sport.
        """
        valid = {t.value for t in Topic}
        fallback = (
            fallback_topic if fallback_topic in valid else Topic.RUSSIA.value
        )
        cleaned = result.strip().lower()
        if not cleaned:
            logger.warning("Empty classification response, using fallback")
            return fallback

        words = cleaned.replace(",", " ").split()
        for raw_word in words:
            word = raw_word.strip(".,!?:;\"'«»")
            if word in valid:
                return word

        logger.warning("Invalid classification", result=result, fallback=fallback)
        return fallback
