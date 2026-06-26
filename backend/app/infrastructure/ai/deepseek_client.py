"""Клиент DeepSeek API с rate limiting."""

import asyncio
import threading
import time

import re

import httpx
from loguru import logger

from app.core.config import get_settings
from app.domain.ai_errors import DeepSeekAuthError

_PLACEHOLDER_KEYS = frozenset({"sk-...", "sk-…", "your_api_key", "change_me"})

_last_request_time: float = 0.0
# threading.Lock: Celery на каждую задачу создаёт новый loop через asyncio.run().
_thread_rate_lock = threading.Lock()
_MIN_INTERVAL = 1.0


class DeepSeekClient:
    """Асинхронный клиент DeepSeek (OpenAI-compatible API)."""

    def __init__(self) -> None:
        settings = get_settings()
        self._api_key = settings.deepseek_api_key
        self._base_url = settings.deepseek_api_base.rstrip("/")
        self._model = settings.deepseek_model

    async def _rate_limit(self) -> None:
        """Ограничение: не чаще 1 запроса в секунду."""
        global _last_request_time
        while True:
            wait_seconds = 0.0
            with _thread_rate_lock:
                now = time.monotonic()
                elapsed = now - _last_request_time
                if elapsed >= _MIN_INTERVAL:
                    _last_request_time = now
                    return
                wait_seconds = _MIN_INTERVAL - elapsed
            await asyncio.sleep(wait_seconds)

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        *,
        temperature: float = 0.7,
        model: str | None = None,
        json_mode: bool = False,
    ) -> str:
        """Вызов chat/completions.

        Args:
            system_prompt: системный промпт.
            user_prompt: пользовательский промпт.
            max_tokens: лимит токенов.
            temperature: температура генерации.
            model: переопределение модели (например deepseek-chat для JSON).
            json_mode: принудительный JSON-ответ (response_format json_object).

        Returns:
            str: текст ответа модели.

        Raises:
            RuntimeError: при ошибке API.
        """
        key = self._api_key.strip()
        if not key or key in _PLACEHOLDER_KEYS or len(key) < 20:
            msg = (
                "DEEPSEEK_API_KEY не задан или оставлен плейсхолдер sk-... "
                "в .env — создайте ключ на https://platform.deepseek.com"
            )
            raise DeepSeekAuthError(msg)

        await self._rate_limit()
        url = f"{self._base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, object] = {
            "model": model or self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 401:
                logger.error(
                    "DeepSeek API authentication failed",
                    status=401,
                    body=response.text[:500],
                )
                msg = (
                    "DeepSeek API: неверный DEEPSEEK_API_KEY (401). "
                    "Проверьте ключ на https://platform.deepseek.com и "
                    "перезапустите: docker compose restart celery_worker backend"
                )
                raise DeepSeekAuthError(msg)
            if response.status_code != 200:
                logger.error(
                    "DeepSeek API error",
                    status=response.status_code,
                    body=response.text[:500],
                )
                msg = f"DeepSeek API error: {response.status_code}"
                raise RuntimeError(msg)
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                msg = "DeepSeek API: пустой ответ (нет choices)"
                raise RuntimeError(msg)
            message = choices[0].get("message") or {}
            finish = choices[0].get("finish_reason")
            content = self._extract_message_text(message, json_mode=json_mode)
            if not content:
                logger.warning(
                    "DeepSeek API: пустой текст ответа",
                    model=model or self._model,
                    finish_reason=finish,
                    max_tokens=max_tokens,
                )
                msg = "DeepSeek API: пустой content в ответе"
                raise RuntimeError(msg)
            if finish == "length":
                logger.warning(
                    "DeepSeek API: ответ обрезан по max_tokens",
                    model=model or self._model,
                    max_tokens=max_tokens,
                    chars=len(content),
                )
            return content

    async def chat_completion_with_meta(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 2000,
        *,
        temperature: float = 0.7,
        model: str | None = None,
        json_mode: bool = False,
    ) -> tuple[str, str | None]:
        """Вызов chat/completions с причиной завершения генерации.

        Args:
            system_prompt: системный промпт.
            user_prompt: пользовательский промпт.
            max_tokens: лимит токенов.
            temperature: температура генерации.
            model: переопределение модели.
            json_mode: принудительный JSON-ответ.

        Returns:
            tuple[str, str | None]: текст ответа и finish_reason.

        Raises:
            RuntimeError: при ошибке API.
            DeepSeekAuthError: при неверном ключе.
        """
        key = self._api_key.strip()
        if not key or key in _PLACEHOLDER_KEYS or len(key) < 20:
            msg = (
                "DEEPSEEK_API_KEY не задан или оставлен плейсхолдер sk-... "
                "в .env — создайте ключ на https://platform.deepseek.com"
            )
            raise DeepSeekAuthError(msg)

        await self._rate_limit()
        url = f"{self._base_url}/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, object] = {
            "model": model or self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 401:
                logger.error(
                    "DeepSeek API authentication failed",
                    status=401,
                    body=response.text[:500],
                )
                msg = (
                    "DeepSeek API: неверный DEEPSEEK_API_KEY (401). "
                    "Проверьте ключ на https://platform.deepseek.com и "
                    "перезапустите: docker compose restart celery_worker backend"
                )
                raise DeepSeekAuthError(msg)
            if response.status_code != 200:
                logger.error(
                    "DeepSeek API error",
                    status=response.status_code,
                    body=response.text[:500],
                )
                msg = f"DeepSeek API error: {response.status_code}"
                raise RuntimeError(msg)
            data = response.json()
            choices = data.get("choices") or []
            if not choices:
                msg = "DeepSeek API: пустой ответ (нет choices)"
                raise RuntimeError(msg)
            message = choices[0].get("message") or {}
            finish = choices[0].get("finish_reason")
            if isinstance(finish, str):
                finish_reason: str | None = finish
            else:
                finish_reason = None
            content = self._extract_message_text(message, json_mode=json_mode)
            if not content:
                logger.warning(
                    "DeepSeek API: пустой текст ответа",
                    model=model or self._model,
                    finish_reason=finish_reason,
                    max_tokens=max_tokens,
                )
                msg = "DeepSeek API: пустой content в ответе"
                raise RuntimeError(msg)
            if finish_reason == "length":
                logger.warning(
                    "DeepSeek API: ответ обрезан по max_tokens",
                    model=model or self._model,
                    max_tokens=max_tokens,
                    chars=len(content),
                )
            return content, finish_reason

    @staticmethod
    def _extract_message_text(
        message: dict[str, object],
        *,
        json_mode: bool = False,
    ) -> str:
        """Извлекает текст ответа из message (content или reasoning_content).

        Args:
            message: объект message из choices API.
            json_mode: если True — ищем JSON с полями статьи/темы.

        Returns:
            str: текст для парсинга.
        """
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        reasoning = message.get("reasoning_content")
        if isinstance(reasoning, str) and reasoning.strip():
            markers = ("title", "topic", "id") if json_mode else ("id", "topic", "title")
            for marker in markers:
                json_blob = DeepSeekClient._extract_json_blob(reasoning, marker=marker)
                if json_blob:
                    return json_blob
            return reasoning.strip()
        return ""

    @staticmethod
    def _extract_json_blob(text: str, *, marker: str = "id") -> str:
        """Ищет JSON-объект с указанным полем в тексте.

        Args:
            text: content или reasoning_content.
            marker: имя поля-маркера (id, topic, title).

        Returns:
            str: найденный JSON или пустая строка.
        """
        pattern = rf'\{{[^{{}}]*"{re.escape(marker)}"\s*:\s*[^}}]+\}}'
        matches = list(re.finditer(pattern, text, re.DOTALL))
        if matches:
            return matches[-1].group(0).strip()
        # Вложенный JSON (длинный body_html): от последней { до конца или до ```
        start = text.rfind("{")
        if start < 0:
            return ""
        tail = text[start:].strip()
        if f'"{marker}"' not in tail:
            return ""
        return tail
