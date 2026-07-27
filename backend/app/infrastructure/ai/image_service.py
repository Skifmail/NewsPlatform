"""Выбор и генерация изображений для постов."""

import base64
from dataclasses import dataclass
from io import BytesIO

import httpx
from loguru import logger
from openai import AsyncOpenAI
from PIL import Image

from app.core.config import get_settings
from app.domain.enums import ImageSource
from app.domain.platform_settings import _parse_bool, clamp_postcard_animation_duration
from app.infrastructure.ai.devtools_teaser_formatter import is_devtools_article_channel
from app.infrastructure.ai.openai_key_chain import active_openai_key
from app.infrastructure.ai.paragraph_teaser_formatter import is_paragraph_article_channel
from app.infrastructure.ai.openrouter_video_client import OpenRouterVideoClient
from app.infrastructure.ai.postcard_teaser_formatter import is_postcard_article_channel
from app.infrastructure.ai.image_prompt_builder import ImagePromptBuilder
from app.infrastructure.ai.logo_compositor import build_github_logo_cover
from app.infrastructure.media_store import is_local_media_url, read_media, save_media
from app.infrastructure.ai.qwen_image_chain import (
    resolve_edit_models,
    resolve_generate_models,
)
from app.infrastructure.ai.qwen_image_client import QwenImageClient
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.raw_post import RawPost
from app.infrastructure.parsers.github_repo_logo import parse_github_repo
from app.infrastructure.parsers.image_extract import (
    extract_image_from_html,
    is_social_preview_image,
)

_USER_AGENT = "Mozilla/5.0 (compatible; NewsPlatform/1.0)"
_PAGE_FETCH_TIMEOUT = 20.0
_OPENAI_POSTCARD_TIMEOUT_SECONDS = 180.0

# Не-растровые/непригодные для Telegram и Pillow форматы. SVG особенно важен:
# CNews отдаёт на каждую статью placeholder-SVG, Pillow его не открывает →
# пост уходил без фото. Такой «оригинал» игнорируем и генерируем обложку.
_NON_RASTER_SUFFIXES = (".svg", ".pdf", ".doc", ".docx", ".ppt", ".pptx")


def _is_raster_image_url(url: str) -> bool:
    """URL ведёт на растровое изображение, пригодное для Pillow/Telegram.

    Args:
        url: ссылка на изображение.

    Returns:
        bool: False для SVG/документов (по расширению без query).
    """
    path = url.lower().split("?", 1)[0].split("#", 1)[0]
    return not path.endswith(_NON_RASTER_SUFFIXES)


@dataclass(frozen=True)
class ImageGenPrompts:
    """Промпты генерации обложек из панели промптов (negative.*, image.cover_prompt)."""

    no_text_negative: str
    news_negative: str
    cover_template: str
    postcard_cover_template: str
    postcard_animation_template: str = ""


class ImageService:
    """Определяет изображение для публикации.

    Для путей генерации требуется ``prompts`` (негативы и шаблон обложки из БД);
    без них доступны только скачивание/обработка готовых изображений.
    """

    def __init__(
        self,
        *,
        generate_models: list[str] | None = None,
        edit_models: list[str] | None = None,
        openai_db_key: str | None = None,
        openrouter_api_key: str | None = None,
        openrouter_video_model: str = "x-ai/grok-imagine-video",
        postcard_animation_enabled: bool = True,
        postcard_animation_duration: int = 2,
        prompts: ImageGenPrompts | None = None,
    ) -> None:
        self._qwen = QwenImageClient()
        self._generate_models = generate_models
        self._edit_models = edit_models
        self._openai_db_key = openai_db_key
        self._openrouter_api_key = (openrouter_api_key or "").strip()
        self._openrouter_video_model = (openrouter_video_model or "x-ai/grok-imagine-video").strip()
        self._postcard_animation_enabled = postcard_animation_enabled
        self._postcard_animation_duration = clamp_postcard_animation_duration(
            postcard_animation_duration
        )
        self._prompts = prompts

    @classmethod
    def from_settings_dict(
        cls,
        merged: dict[str, str] | None = None,
        *,
        prompts: ImageGenPrompts | None = None,
    ) -> "ImageService":
        """Создаёт сервис с цепочками моделей из настроек платформы."""
        generate_raw = merged.get("qwen_image_models") if merged else None
        edit_raw = merged.get("qwen_image_edit_models") if merged else None
        openai_key = active_openai_key(merged.get("openai_api_keys")) if merged else None
        openrouter_key = ""
        animation_enabled = True
        video_model = "x-ai/grok-imagine-video"
        animation_duration = 2
        if merged:
            openrouter_key = (merged.get("openrouter_api_key") or "").strip()
            animation_enabled = _parse_bool(
                merged.get("postcard_animation_enabled", "true"), True
            )
            video_model = (
                merged.get("openrouter_video_model") or "x-ai/grok-imagine-video"
            )
            animation_duration = clamp_postcard_animation_duration(
                merged.get("postcard_animation_duration", "2")
            )
        if not openrouter_key:
            openrouter_key = get_settings().openrouter_api_key.strip()
        return cls(
            generate_models=resolve_generate_models(generate_raw),
            edit_models=resolve_edit_models(edit_raw),
            openai_db_key=openai_key,
            openrouter_api_key=openrouter_key or None,
            openrouter_video_model=video_model,
            postcard_animation_enabled=animation_enabled,
            postcard_animation_duration=animation_duration,
            prompts=prompts,
        )

    def _require_prompts(self) -> ImageGenPrompts:
        """Промпты генерации, обязательные для AI-путей.

        Raises:
            RuntimeError: сервис создан без промптов (проверьте панель промптов).
        """
        if self._prompts is None:
            msg = (
                "ImageService создан без промптов генерации (negative.*, "
                "image.cover_prompt) — передайте prompts из PromptService."
            )
            raise RuntimeError(msg)
        return self._prompts

    @staticmethod
    def ai_generation_available() -> bool:
        """Проверяет, настроена ли хотя бы одна модель генерации изображений.

        Returns:
            bool: True если задан Qwen или OpenAI ключ.
        """
        settings = get_settings()
        return bool(
            settings.qwen_image_api_key.strip() or settings.openai_api_key.strip()
        )

    async def resolve_image(
        self,
        raw_post: RawPost,
        channel: Channel,
        generate_if_missing: bool = False,
    ) -> tuple[str | None, str]:
        """Возвращает URL изображения и источник.

        Args:
            raw_post: сырой пост.
            generate_if_missing: генерировать AI-обложку если нет оригинала.

        Returns:
            tuple[str | None, str]: URL и image_source.
        """
        stored = raw_post.image_url
        # Растровый оригинал (не SVG/документ и не telegram://).
        stored_ok = bool(
            stored
            and not stored.startswith("telegram://")
            and _is_raster_image_url(stored)
        )

        if stored_ok and not is_social_preview_image(stored):
            return stored, ImageSource.ORIGINAL.value

        # Оригинал негоден (SVG-заглушка cnews) или это соцпревью — пробуем
        # og:image со страницы статьи.
        if raw_post.url:
            page_image = await self._fetch_page_image(raw_post.url)
            if (
                page_image
                and _is_raster_image_url(page_image)
                and not is_social_preview_image(page_image)
            ):
                return page_image, ImageSource.ORIGINAL.value

        # Растровое соцпревью — лучше, чем ничего (но SVG сюда не попадёт).
        if stored_ok:
            return stored, ImageSource.ORIGINAL.value

        if generate_if_missing:
            generated = await self._generate_for_post(raw_post, channel)
            if generated:
                return generated, ImageSource.GENERATED.value

        return None, ImageSource.NONE.value

    async def _fetch_page_image(self, page_url: str) -> str | None:
        """Подтягивает og:image / первую картинку со страницы статьи.

        Args:
            page_url: URL оригинальной новости.

        Returns:
            str | None: URL изображения.
        """
        try:
            async with httpx.AsyncClient(
                timeout=_PAGE_FETCH_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                resp = await client.get(page_url)
                resp.raise_for_status()
            return extract_image_from_html(resp.text, page_url)
        except Exception as exc:
            logger.debug(
                "Page image fetch skipped",
                url=page_url,
                error=str(exc),
            )
            return None

    async def generate_from_prompt(self, prompt: str) -> str | None:
        """Генерирует изображение по произвольному промпту.

        Args:
            prompt: описание сцены.

        Returns:
            str | None: URL изображения.
        """
        text = prompt.strip()
        if not text:
            return None
        return await self._generate_ai_image(text)

    async def resolve_article_image(
        self,
        *,
        channel: Channel,
        article_title: str,
        topic: str,
        image_prompt: str,
        fallback_url: str | None = None,
        repo_url: str | None = None,
        teaser: str = "",
        greeting_text: str = "",
    ) -> tuple[str | None, str]:
        """Подбирает обложку для статьи.

        Args:
            channel: канал публикации.
            article_title: заголовок статьи.
            topic: тема статьи.
            image_prompt: черновик сцены от ArticleWriter.
            fallback_url: URL из первого источника (не PDF и не документ).
            repo_url: ссылка на GitHub-репозиторий (для логотипа).
            greeting_text: надпись на русском для рендера на открытке (только postcard).

        Returns:
            tuple[str | None, str]: URL и image_source.
        """
        tool_name = ImagePromptBuilder.extract_tool_name(article_title, topic)
        if (
            repo_url
            and is_devtools_article_channel(channel.topic, channel.name)
        ):
            composed = await build_github_logo_cover(repo_url)
            if composed:
                logger.info(
                    "Github cover composed from real logo",
                    repo_url=repo_url,
                )
                return composed, ImageSource.GENERATED.value

            parsed = parse_github_repo(repo_url)
            if parsed:
                owner, repo = parsed
                og_url = (
                    f"https://opengraph.githubassets.com/1/{owner}/{repo}"
                )
                logger.info(
                    "Logo composite unavailable, falling back to GitHub OG preview",
                    owner=owner,
                    repo=repo,
                    og_url=og_url,
                )
                return og_url, ImageSource.ORIGINAL.value

        generated = None
        if is_postcard_article_channel(channel.name, channel.topic):
            cover_prompt = ImagePromptBuilder.build_postcard_cover_prompt(
                template=self._require_prompts().postcard_cover_template,
                title=article_title,
                scene=image_prompt,
                greeting_text=greeting_text,
            )
            logger.debug("Postcard cover prompt", preview=cover_prompt[:200])
            generated = await self._generate_postcard_dalle_cover(cover_prompt)
            if not generated:
                # Qwen не умеет рендерить текст — безопасный фолбэк без надписи.
                qwen_prompt = ImagePromptBuilder.build_for_qwen(
                    channel,
                    article_title=article_title,
                    topic=topic,
                    draft_image_prompt=image_prompt,
                )
                generated = await self._generate_with_qwen_constraints(qwen_prompt or "")
        elif is_paragraph_article_channel(channel.name):
            cover_prompt = ImagePromptBuilder.build_cover_prompt(
                template=self._require_prompts().cover_template,
                article_title=article_title,
                draft_image_prompt=image_prompt,
                teaser=teaser,
            )
            logger.debug("Paragraph cover prompt", preview=cover_prompt[:200])
            generated = await self._generate_dalle_cover(cover_prompt)
            if not generated:
                generated = await self._generate_with_qwen_constraints(
                    ImagePromptBuilder.build_for_qwen(
                        channel,
                        article_title=article_title,
                        topic=topic,
                        draft_image_prompt=image_prompt,
                    ) or ""
                )
        else:
            final_prompt = ImagePromptBuilder.build_for_qwen(
                channel,
                article_title=article_title,
                topic=topic,
                draft_image_prompt=image_prompt,
            )
            if final_prompt:
                logger.debug("Article image prompt built", preview=final_prompt[:200])
                generated = await self._generate_with_qwen_constraints(final_prompt)
            else:
                logger.warning(
                    "Article cover skipped: image_prompt_guidelines is empty",
                    channel_id=channel.id,
                )
        if generated:
            return generated, ImageSource.GENERATED.value
        if fallback_url and self._is_usable_fallback_url(fallback_url):
            return fallback_url, ImageSource.ORIGINAL.value
        return None, ImageSource.NONE.value

    async def _generate_for_post(
        self,
        raw_post: RawPost,
        channel: Channel,
    ) -> str | None:
        """Генерирует иллюстрацию для новости без картинки в источнике.

        Args:
            raw_post: сырой пост.
            channel: канал публикации.

        Returns:
            str | None: URL изображения.
        """
        prompt = ImagePromptBuilder.build_for_news(
            channel,
            raw_post.title or "",
            raw_post.content,
        )
        return await self._generate_news_image(prompt)

    async def _generate_news_image(self, prompt: str | None) -> str | None:
        """Генерирует обложку новости с анти-портретными ограничениями."""
        if not prompt:
            return None
        settings = get_settings()
        if settings.qwen_image_api_key.strip():
            try:
                url = await self._qwen.generate(
                    prompt,
                    prompt_extend=False,
                    negative_prompt=self._require_prompts().news_negative,
                    models=self._generate_models,
                )
                if url:
                    return url
            except Exception as exc:
                logger.warning("Qwen Image generation failed", error=str(exc))
        return await self._generate_dalle(prompt)

    async def _generate_postcard_dalle_cover(
        self,
        prompt: str | None,
    ) -> str | None:
        """Generate a postcard via direct gpt-image-2 (text on image allowed)."""
        if not prompt:
            return None
        return await self._call_openai_image(
            prompt[:2000],
            size="1024x1536",
            quality="high",
        )

    async def _generate_with_qwen_constraints(self, prompt: str | None) -> str | None:
        """Генерирует изображение через Qwen без текста на картинке.

        Args:
            prompt: финальный промпт.

        Returns:
            str | None: URL изображения.
        """
        if not prompt:
            return None
        settings = get_settings()
        if settings.qwen_image_api_key.strip():
            try:
                url = await self._qwen.generate(
                    prompt,
                    prompt_extend=False,
                    negative_prompt=self._require_prompts().no_text_negative,
                    models=self._generate_models,
                )
                if url:
                    return url
            except Exception as exc:
                logger.warning("Qwen Image generation failed", error=str(exc))
        return await self._generate_dalle(prompt)

    async def _generate_ai_image(self, prompt: str) -> str | None:
        """Генерирует изображение: Qwen-Image → fallback OpenAI.

        Args:
            prompt: текстовый промпт.

        Returns:
            str | None: URL изображения.
        """
        settings = get_settings()
        if settings.qwen_image_api_key.strip():
            try:
                url = await self._qwen.generate(
                    prompt,
                    prompt_extend=False,
                    negative_prompt=self._require_prompts().no_text_negative,
                    models=self._generate_models,
                )
                if url:
                    return url
            except Exception as exc:
                logger.warning("Qwen Image generation failed", error=str(exc))

        if settings.openai_api_key.strip():
            return await self._generate_dalle(prompt)

        logger.warning("No image generation API configured (QWEN_IMAGE_API_KEY / OPENAI_API_KEY)")
        return None

    async def _generate_dalle(self, prompt: str) -> str | None:
        """Генерирует изображение через OpenAI gpt-image-2 (без текста)."""
        full_prompt = (
            f"{prompt[:900]}. "
            "Absolutely no text, letters, words, captions or watermarks on the image."
        )
        return await self._call_openai_image(full_prompt)

    async def _generate_dalle_cover(self, prompt: str) -> str | None:
        """Генерирует обложку с текстом через OpenAI gpt-image-2.

        НЕ запрещает текст — gpt-image-2 умеет рендерить типографику.
        """
        return await self._call_openai_image(
            prompt[:1500], size="1536x1024", quality="high",
        )

    async def _call_openai_image(
        self,
        prompt: str,
        *,
        size: str = "1024x1024",
        quality: str = "medium",
    ) -> str | None:
        api_key = self._openai_db_key or get_settings().openai_api_key.strip()
        if not api_key:
            return None
        try:
            async with AsyncOpenAI(
                api_key=api_key,
                timeout=_OPENAI_POSTCARD_TIMEOUT_SECONDS,
                max_retries=1,
            ) as client:
                response = await client.images.generate(
                    model="gpt-image-2",
                    prompt=prompt,
                    size=size,
                    quality=quality,
                    n=1,
                )
            b64 = response.data[0].b64_json
            if not b64:
                logger.warning("OpenAI image: empty b64_json")
                return None
            image_bytes = base64.b64decode(b64, validate=True)
            return save_media(image_bytes, "covers", ".png")
        except Exception as exc:
            logger.error("OpenAI image generation failed", error=str(exc))
            return None

    @staticmethod
    def _is_usable_fallback_url(url: str) -> bool:
        """Проверяет, что URL похож на изображение, а не на PDF/документ.

        Args:
            url: ссылка из источника.

        Returns:
            bool: True если URL можно использовать как картинку.
        """
        lowered = url.lower().split("?", 1)[0]
        blocked = (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".zip")
        return not lowered.endswith(blocked)


    async def maybe_animate_postcard(
        self,
        *,
        channel: Channel,
        image_url: str | None,
        article_title: str,
    ) -> str | None:
        """Animate a postcard still via OpenRouter when enabled for the channel."""
        if not image_url:
            return None
        if not is_postcard_article_channel(channel.name, channel.topic):
            return None
        if not getattr(channel, "animate_postcards", False):
            return None
        if not self._postcard_animation_enabled:
            return None
        if not self._openrouter_api_key:
            logger.warning("Postcard animation skipped: OpenRouter API key missing")
            return None

        template = (self._require_prompts().postcard_animation_template or "").strip()
        if not template:
            template = (
                "Деликатно анимируй сцену на открытке «{title}». "
                "Двигаются только объекты сцены. "
                "Текст и надписи остаются абсолютно неподвижными."
            )
        from app.utils.safe_format import safe_format

        motion_prompt = safe_format(template, title=article_title.strip())
        image_bytes = read_media(image_url)
        if not image_bytes:
            logger.warning("Postcard animation skipped: image not found", url=image_url)
            return None

        try:
            client = OpenRouterVideoClient(
                api_key=self._openrouter_api_key,
                model=self._openrouter_video_model,
            )
            result = await client.animate_image(
                image_bytes=image_bytes,
                prompt=motion_prompt,
                duration=self._postcard_animation_duration,
            )
        except Exception as exc:
            logger.warning(
                "Postcard animation failed; publishing static image",
                error=str(exc),
                channel_id=channel.id,
            )
            return None

        suffix = ".mp4" if "mp4" in result.content_type else ".mp4"
        video_url = save_media(result.video_bytes, "animations", suffix)
        logger.info(
            "Postcard animated",
            channel_id=channel.id,
            job_id=result.job_id,
            video_url=video_url,
        )
        return video_url

    async def download_media_bytes(self, media_url: str) -> bytes | None:
        """Download raw media bytes (image or video) without transcoding."""
        if is_local_media_url(media_url):
            return read_media(media_url)
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.get(media_url)
                resp.raise_for_status()
            return resp.content
        except Exception as exc:
            logger.warning("Media download failed", url=media_url, error=str(exc))
            return None

    async def download_and_resize(
        self, image_url: str, max_size: tuple[int, int] = (1280, 1280)
    ) -> bytes | None:
        """Скачивает и ресайзит изображение.

        Args:
            image_url: URL картинки.
            max_size: максимальный размер.

        Returns:
            bytes | None: JPEG bytes.
        """
        try:
            if is_local_media_url(image_url):
                # Обложка, собранная logo_compositor'ом на общем volume —
                # уже готовый JPEG, без HTTP-скачивания.
                raw = read_media(image_url)
                if raw is None:
                    logger.warning("Local media not found", url=image_url)
                    return None
                img = Image.open(BytesIO(raw))
                img = img.convert("RGB")
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                buffer = BytesIO()
                img.save(buffer, format="JPEG", quality=85)
                return buffer.getvalue()

            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(image_url)
                resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").lower()
            if content_type and not content_type.startswith("image/"):
                logger.warning(
                    "Image download skipped: not an image",
                    url=image_url,
                    content_type=content_type,
                )
                return None
            # SVG проходит startswith("image/"), но Pillow его не откроет.
            if "svg" in content_type:
                logger.debug("Image skipped: SVG not supported", url=image_url)
                return None
            img = Image.open(BytesIO(resp.content))
            img = img.convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            buffer = BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            return buffer.getvalue()
        except Exception as exc:
            logger.warning("Image download failed", url=image_url, error=str(exc))
            return None
