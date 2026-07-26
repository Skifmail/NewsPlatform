"""Выбор лучшего материала для публикации по тематике."""

import json
import re

from loguru import logger

from app.core.config import get_settings
from app.domain.curated_pick import TOPIC_LABELS, TopicPickResult
from app.infrastructure.ai.deepseek_client import DeepSeekClient
from app.infrastructure.models.raw_post import RawPost
from app.utils.safe_format import safe_format

_PREVIEW_LEN = 320
_SINGLE_CANDIDATE_REASON = "Единственный необработанный материал в очереди."
_FALLBACK_REASON = "Ответ модели не распознан — выбран самый свежий материал."
_ERROR_REASON = "Ошибка выбора модели — выбран самый свежий материал."
_ID_ONLY_REASON = "Модель указала id без обоснования."


class TopicPicker:
    """Выбирает один raw_post для рерайта и публикации."""

    def __init__(self, client: DeepSeekClient | None = None) -> None:
        self._client = client or DeepSeekClient()

    async def pick_best(
        self,
        topic: str,
        candidates: list[RawPost],
        prompt_template: str,
        system_prompt: str,
    ) -> TopicPickResult | None:
        """Определяет наиболее подходящий материал и обоснование выбора.

        Args:
            topic: тема it | auto | russia.
            candidates: необработанные raw_posts (новые первыми).
            prompt_template: шаблон с {topic_label} и {candidates}.
            system_prompt: системный промпт выбора (из панели промптов).

        Returns:
            TopicPickResult | None: выбор с причиной или None если список пуст.
        """
        if not candidates:
            return None

        post_by_id = {post.id: post for post in candidates}
        if len(candidates) == 1:
            only = candidates[0]
            return self._to_result(only, _SINGLE_CANDIDATE_REASON)

        topic_label = TOPIC_LABELS.get(topic, topic)
        lines: list[str] = []
        for post in candidates:
            source_name = post.source.name if post.source else "—"
            title = (post.title or "").strip() or "Без заголовка"
            preview = " ".join(post.content.split())[:_PREVIEW_LEN]
            lines.append(f"#{post.id} | {source_name} | {title}\n{preview}")
        candidates_text = "\n\n".join(lines)
        prompt = safe_format(
            prompt_template,
            topic_label=topic_label,
            topic=topic,
            candidates=candidates_text,
        )
        settings = get_settings()
        try:
            result = await self._client.chat_completion(
                system_prompt=system_prompt,
                user_prompt=prompt,
                max_tokens=4000,
                temperature=0.2,
                model=settings.deepseek_model,
            )
            parsed = self._parse_pick_response(result, set(post_by_id))
            if parsed is not None:
                post = post_by_id[parsed.raw_post_id]
                logger.info(
                    "Curated topic pick",
                    topic=topic,
                    raw_post_id=parsed.raw_post_id,
                    reason=parsed.reason,
                    candidates=len(candidates),
                    model=settings.deepseek_model,
                )
                return self._to_result(post, parsed.reason)
            logger.warning(
                "Curated pick response not parsed: {preview}",
                topic=topic,
                candidates=len(candidates),
                model=settings.deepseek_model,
                preview=result[:500],
            )
        except Exception as exc:
            logger.warning(
                "Topic pick failed, using newest candidate",
                topic=topic,
                error=str(exc),
            )
            return self._to_result(candidates[0], _ERROR_REASON)

        return self._to_result(candidates[0], _FALLBACK_REASON)

    @staticmethod
    def _to_result(post: RawPost, reason: str) -> TopicPickResult:
        """Собирает результат выбора из raw_post.

        Args:
            post: выбранный материал.
            reason: обоснование выбора.

        Returns:
            TopicPickResult: итог для журнала и UI.
        """
        source_name = post.source.name if post.source else "—"
        title = (post.title or "").strip() or "Без заголовка"
        return TopicPickResult(
            raw_post_id=post.id,
            reason=reason.strip() or _FALLBACK_REASON,
            title=title,
            source_name=source_name,
        )

    @staticmethod
    def _parse_pick_response(
        result: str,
        valid_ids: set[int],
    ) -> TopicPickResult | None:
        """Извлекает id и reason из ответа модели.

        Args:
            result: сырой ответ.
            valid_ids: допустимые id.

        Returns:
            TopicPickResult | None: распознанный выбор без title/source.
        """
        cleaned = result.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)

        for blob in TopicPicker._json_candidates(cleaned):
            parsed = TopicPicker._parse_json_blob(blob, valid_ids)
            if parsed is not None:
                return parsed

        id_reason = TopicPicker._parse_id_reason_fields(cleaned, valid_ids)
        if id_reason is not None:
            return id_reason

        hash_ids = [
            int(value)
            for value in re.findall(r"#(\d+)", cleaned)
            if int(value) in valid_ids
        ]
        if hash_ids:
            return TopicPickResult(
                raw_post_id=hash_ids[-1],
                reason=_ID_ONLY_REASON,
                title="",
                source_name="",
            )

        if cleaned.isdigit():
            value = int(cleaned)
            if value in valid_ids:
                return TopicPickResult(
                    raw_post_id=value,
                    reason=_ID_ONLY_REASON,
                    title="",
                    source_name="",
                )

        return None

    @staticmethod
    def _json_candidates(text: str) -> list[str]:
        """Собирает возможные JSON-фрагменты из ответа.

        Args:
            text: сырой ответ модели.

        Returns:
            list[str]: кандидаты для json.loads.
        """
        candidates: list[str] = [text.strip()]
        candidates.extend(
            match.group(0)
            for match in re.finditer(
                r'\{[^{}]*"id"\s*:\s*[^}]+\}',
                text,
                re.DOTALL,
            )
        )
        return candidates

    @staticmethod
    def _parse_json_blob(blob: str, valid_ids: set[int]) -> TopicPickResult | None:
        """Парсит один JSON-объект с полями id и reason.

        Args:
            blob: JSON-строка.
            valid_ids: допустимые id.

        Returns:
            TopicPickResult | None: распознанный выбор.
        """
        try:
            data = json.loads(blob)
        except (json.JSONDecodeError, TypeError, ValueError):
            return None
        if not isinstance(data, dict) or "id" not in data:
            return None
        post_id = TopicPicker._coerce_id(data["id"])
        if post_id is None or post_id not in valid_ids:
            return None
        reason = str(data.get("reason", "")).strip() or _ID_ONLY_REASON
        return TopicPickResult(
            raw_post_id=post_id,
            reason=reason,
            title="",
            source_name="",
        )

    @staticmethod
    def _parse_id_reason_fields(
        text: str,
        valid_ids: set[int],
    ) -> TopicPickResult | None:
        """Извлекает id и reason regex-ом без полного JSON.

        Args:
            text: сырой ответ.
            valid_ids: допустимые id.

        Returns:
            TopicPickResult | None: распознанный выбор.
        """
        id_match = re.search(r'"id"\s*:\s*"?#?(\d+)"?', text)
        if not id_match:
            return None
        post_id = int(id_match.group(1))
        if post_id not in valid_ids:
            return None
        reason_match = re.search(
            r'"reason"\s*:\s*"((?:[^"\\]|\\.)*)"',
            text,
            re.DOTALL,
        )
        reason = reason_match.group(1).strip() if reason_match else _ID_ONLY_REASON
        return TopicPickResult(
            raw_post_id=post_id,
            reason=reason,
            title="",
            source_name="",
        )

    @staticmethod
    def _coerce_id(value: object) -> int | None:
        """Приводит id из JSON к int.

        Args:
            value: значение поля id.

        Returns:
            int | None: распознанный id.
        """
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            cleaned = value.strip().lstrip("#")
            if cleaned.isdigit():
                return int(cleaned)
        return None
