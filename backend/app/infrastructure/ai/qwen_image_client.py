"""Клиент генерации изображений Qwen-Image (DashScope API)."""

from dataclasses import dataclass
from typing import Any

import httpx
from loguru import logger

from app.core.config import get_settings
from app.infrastructure.ai.image_prompt_builder import QWEN_NO_TEXT_NEGATIVE
from app.infrastructure.ai.qwen_image_chain import (
    is_invalid_size_error,
    is_model_exhausted,
    is_quota_exhausted,
    mark_model_exhausted,
    resolve_edit_models,
    resolve_generate_models,
    sizes_for_model,
)

_DEFAULT_NEGATIVE_PROMPT = QWEN_NO_TEXT_NEGATIVE


@dataclass(frozen=True)
class QwenImageResult:
    """Результат генерации или редактирования."""

    url: str
    model: str


class QwenImageClient:
    """Генерирует изображения через Qwen-Image multimodal-generation API."""

    async def generate(
        self,
        prompt: str,
        *,
        size: str | None = None,
        prompt_extend: bool = True,
        negative_prompt: str | None = None,
        models: list[str] | None = None,
    ) -> str | None:
        """Создаёт изображение по текстовому промпту с fallback по моделям.

        Returns:
            str | None: URL PNG или None при ошибке всех моделей.
        """
        result = await self.generate_with_meta(
            prompt,
            size=size,
            prompt_extend=prompt_extend,
            negative_prompt=negative_prompt,
            models=models,
        )
        return result.url if result else None

    async def generate_with_meta(
        self,
        prompt: str,
        *,
        size: str | None = None,
        prompt_extend: bool = True,
        negative_prompt: str | None = None,
        models: list[str] | None = None,
    ) -> QwenImageResult | None:
        """Генерация с указанием модели, которая сработала."""
        chain = models or resolve_generate_models()
        return await self._run_chain(
            chain,
            build_payload=lambda model, resolved_size: self._build_generate_payload(
                model,
                prompt,
                resolved_size,
                prompt_extend=prompt_extend,
                negative_prompt=negative_prompt,
            ),
            size=size,
            operation="generate",
        )

    async def edit(
        self,
        reference_image_url: str,
        prompt: str,
        *,
        size: str | None = None,
        prompt_extend: bool = True,
        negative_prompt: str | None = None,
        models: list[str] | None = None,
    ) -> str | None:
        """Стилизует изображение по референсу (логотип → обложка)."""
        result = await self.edit_with_meta(
            reference_image_url,
            prompt,
            size=size,
            prompt_extend=prompt_extend,
            negative_prompt=negative_prompt,
            models=models,
        )
        return result.url if result else None

    async def edit_with_meta(
        self,
        reference_image_url: str,
        prompt: str,
        *,
        size: str | None = None,
        prompt_extend: bool = True,
        negative_prompt: str | None = None,
        models: list[str] | None = None,
    ) -> QwenImageResult | None:
        """Редактирование с fallback по edit-моделям."""
        chain = models or resolve_edit_models()
        return await self._run_chain(
            chain,
            build_payload=lambda model, resolved_size: self._build_edit_payload(
                model,
                reference_image_url,
                prompt,
                resolved_size,
                prompt_extend=prompt_extend,
                negative_prompt=negative_prompt,
            ),
            size=size,
            operation="edit",
        )

    async def _run_chain(
        self,
        models: list[str],
        *,
        build_payload,
        size: str | None,
        operation: str,
    ) -> QwenImageResult | None:
        settings = get_settings()
        api_key = settings.qwen_image_api_key.strip()
        if not api_key:
            msg = (
                "QWEN_IMAGE_API_KEY не задан — добавьте ключ DashScope/Qwen Image в .env"
            )
            raise RuntimeError(msg)

        default_size = size or settings.qwen_image_size
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        for model in models:
            if is_model_exhausted(model):
                logger.debug("Skipping exhausted Qwen image model", model=model)
                continue

            for resolved_size in sizes_for_model(model, default_size):
                payload = build_payload(model, resolved_size)
                data, status_code, body_text = await self._post(
                    settings.qwen_image_api_base,
                    headers=headers,
                    payload=payload,
                )
                if data is None:
                    if is_quota_exhausted(status_code=status_code, body_text=body_text):
                        mark_model_exhausted(model)
                        logger.warning(
                            "Qwen image quota exhausted, trying next model",
                            model=model,
                            operation=operation,
                            status=status_code,
                        )
                        break
                    continue

                api_code = str(data.get("code") or "")
                message = str(data.get("message") or "")

                if api_code:
                    if is_quota_exhausted(
                        status_code=status_code,
                        body_text=body_text,
                        api_code=api_code or None,
                        message=message or None,
                    ):
                        mark_model_exhausted(model)
                        logger.warning(
                            "Qwen image quota exhausted, trying next model",
                            model=model,
                            operation=operation,
                            code=api_code,
                            message=message[:200],
                        )
                        break

                    if is_invalid_size_error(
                        body_text=body_text,
                        api_code=api_code or None,
                        message=message or None,
                    ):
                        logger.debug(
                            "Qwen image size rejected, retrying",
                            model=model,
                            size=resolved_size,
                        )
                        continue

                    logger.error(
                        "Qwen Image API error",
                        model=model,
                        operation=operation,
                        status=status_code,
                        code=api_code,
                        message=message[:300],
                    )
                    break

                if status_code != 200:
                    break

                url = self._extract_image_url(data)
                if url:
                    logger.info(
                        "Qwen Image succeeded",
                        model=model,
                        operation=operation,
                        size=resolved_size,
                    )
                    return QwenImageResult(url=url, model=model)

                logger.warning(
                    "Qwen Image API: URL не найден в ответе",
                    model=model,
                    operation=operation,
                    preview=str(data)[:400],
                )
                break

        logger.error(
            "All Qwen image models failed",
            operation=operation,
            models=models,
        )
        return None

    @staticmethod
    async def _post(
        url: str,
        *,
        headers: dict[str, str],
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any] | None, int, str]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            body_text = response.text[:2000]
            if response.status_code != 200:
                logger.error(
                    "Qwen Image API HTTP error",
                    status=response.status_code,
                    model=payload.get("model"),
                    body=body_text[:500],
                )
                try:
                    data = response.json()
                except Exception:
                    if is_quota_exhausted(status_code=response.status_code, body_text=body_text):
                        return None, response.status_code, body_text
                    return None, response.status_code, body_text
                api_code = str(data.get("code") or "")
                message = str(data.get("message") or "")
                if is_quota_exhausted(
                    status_code=response.status_code,
                    body_text=body_text,
                    api_code=api_code or None,
                    message=message or None,
                ):
                    return data, response.status_code, body_text
                return None, response.status_code, body_text
            try:
                data = response.json()
            except Exception:
                return None, response.status_code, body_text
            return data, response.status_code, body_text

    @staticmethod
    def _build_generate_payload(
        model: str,
        prompt: str,
        size: str,
        *,
        prompt_extend: bool,
        negative_prompt: str | None,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [{"text": prompt[:800]}],
                    }
                ]
            },
            "parameters": {
                "negative_prompt": negative_prompt or _DEFAULT_NEGATIVE_PROMPT,
                "prompt_extend": prompt_extend,
                "watermark": False,
                "size": size,
            },
        }

    @staticmethod
    def _build_edit_payload(
        model: str,
        reference_image_url: str,
        prompt: str,
        size: str,
        *,
        prompt_extend: bool,
        negative_prompt: str | None,
    ) -> dict[str, Any]:
        return {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": reference_image_url},
                            {"text": prompt[:800]},
                        ],
                    }
                ]
            },
            "parameters": {
                "negative_prompt": negative_prompt or _DEFAULT_NEGATIVE_PROMPT,
                "prompt_extend": prompt_extend,
                "watermark": False,
                "size": size,
            },
        }

    @staticmethod
    def _extract_image_url(data: dict[str, Any]) -> str | None:
        output = data.get("output")
        if not isinstance(output, dict):
            return None
        choices = output.get("choices")
        if not isinstance(choices, list):
            return None
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message")
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if not isinstance(content, list):
                continue
            for item in content:
                if not isinstance(item, dict):
                    continue
                image = item.get("image")
                if isinstance(image, str) and image.startswith("http"):
                    return image
        return None
