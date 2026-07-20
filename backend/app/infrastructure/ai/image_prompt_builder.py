"""Сборка промптов для генерации обложек."""

import re

from loguru import logger

from app.infrastructure.models.channel import Channel

# Общий негативный промпт Qwen — усиленный запрет текста.
QWEN_NO_TEXT_NEGATIVE = (
    "text, letters, words, numbers, typography, caption, headline, title, subtitle, "
    "label, watermark, logo, banner, sign, poster with writing, speech bubble, "
    "channel name, app icon, telegram logo, science-pop, audience, "
    # Запрет UI-рамки/карточки по центру (модель рисует их из-за слова thumbnail).
    "frame, border, rounded rectangle, rounded square, card, UI card, "
    "thumbnail frame, thumbnail card, picture-in-picture, inset panel, "
    "framed image, image inside a frame, translucent overlay, glass panel, "
    "floating window, glassmorphism panel, vignette box, "
    "Cyrillic, Latin alphabet, Chinese characters, gibberish text, "
    "low resolution, low quality, distorted limbs, malformed fingers, "
    "oversaturated colors, blurry."
)

QWEN_NEWS_NEGATIVE = (
    f"{QWEN_NO_TEXT_NEGATIVE}, "
    "portrait, headshot, close-up face, generic man, generic woman, stock photo person, "
    "news anchor, reporter, businessman, office worker, person looking at camera, "
    "selfie, mugshot, passport photo."
)

QWEN_LOGO_EDIT_NEGATIVE = (
    "blurry, low quality, distorted logo, unrecognizable brand, "
    "cluttered background, extra watermark, random gibberish text, "
    "multiple competing logos, meme style, oversaturated, ugly composition."
)

_WRITER_IMAGE_FIELD_HINT = (
    "Поле image_prompt: одно предложение на английском — только визуальная сцена "
    "(предмет, символ, среда). Без слов, надписей и текста на картинке."
)


class ImagePromptBuilder:
    """Формирует промпты обложек только из настроек канала."""

    @staticmethod
    def writer_image_guidelines(channel: Channel) -> str:
        """Краткая инструкция для поля image_prompt в ArticleWriter."""
        _ = channel
        return _WRITER_IMAGE_FIELD_HINT

    @staticmethod
    def build_for_qwen(
        channel: Channel,
        *,
        article_title: str,
        topic: str,
        draft_image_prompt: str,
    ) -> str | None:
        """Собирает финальный промпт Qwen из шаблона канала."""
        tool_name = ImagePromptBuilder.extract_tool_name(article_title, topic)
        scene = ImagePromptBuilder._normalize_scene(draft_image_prompt, tool_name, topic)
        scene = ImagePromptBuilder._sanitize_scene_for_qwen(scene)
        return ImagePromptBuilder.build_for_channel(
            channel,
            scene=scene,
            title=article_title,
            topic=topic,
            tool_name=tool_name,
        )

    @staticmethod
    def build_for_news(
        channel: Channel,
        title: str,
        content: str | None = None,
    ) -> str | None:
        """Промпт обложки новости из шаблона канала."""
        visual_hint = ImagePromptBuilder._visual_hint_from_title(
            title or "",
            content=content,
        )
        tool_name = ImagePromptBuilder.extract_tool_name(title or "", channel.topic)
        return ImagePromptBuilder.build_for_channel(
            channel,
            scene=visual_hint,
            title=title or "",
            topic=channel.topic,
            tool_name=tool_name,
        )

    @staticmethod
    def build_for_channel(
        channel: Channel,
        *,
        scene: str,
        title: str = "",
        topic: str = "",
        tool_name: str = "",
    ) -> str | None:
        """Подставляет плейсхолдеры в промпт обложек из настроек канала.

        Returns:
            str | None: промпт для Qwen или None, если шаблон не задан.
        """
        template = (channel.image_prompt_guidelines or "").strip()
        if not template:
            logger.warning(
                "Cover prompt skipped: image_prompt_guidelines is empty",
                channel_id=channel.id,
                channel_name=channel.name,
            )
            return None

        safe_scene = ImagePromptBuilder._sanitize_scene_for_qwen(scene)
        safe_title = ImagePromptBuilder._strip_cyrillic(title)
        safe_tool = ImagePromptBuilder._strip_cyrillic(tool_name) or safe_scene[:80]
        placeholders = {
            "tool_name": safe_tool,
            "topic": topic or channel.topic,
            "scene": safe_scene,
            "title": safe_title,
        }
        try:
            return template.format(**placeholders)
        except KeyError:
            return f"{template} Scene: {safe_scene}."

    @staticmethod
    def _strip_cyrillic(value: str) -> str:
        """Убирает кириллицу — Qwen рисует её как надпись на картинке."""
        cleaned = re.sub(r"[а-яА-ЯёЁ]+", " ", value or "")
        return re.sub(r"\s{2,}", " ", cleaned).strip()

    @staticmethod
    def _visual_hint_from_title(title: str, *, content: str | None = None) -> str:
        """Переводит тему новости в визуальную сцену на английском."""
        text = " ".join(part for part in (title, content or "") if part).strip()
        lowered = text.lower()
        if any(
            marker in lowered
            for marker in ("ребён", "ребен", "дет", "малыш", "мальчик", "девочк")
        ) and any(
            marker in lowered
            for marker in ("машин", "авто", "ком", "тепл", "жар", "заперт")
        ):
            return (
                "a child in distress inside a sun-heated parked car, "
                "seen through the side window, heat shimmer and harsh sunlight"
            )
        if any(
            marker in lowered
            for marker in ("вагон", "рельс", "поезд", "ж/д", "жд ", "железнодор", "электричк")
        ):
            return (
                "derailed freight train cars on railway tracks in open countryside, "
                "wide shot, overcast sky, no people"
            )
        if any(
            marker in lowered
            for marker in ("аэропорт", "рейс", "авиакомпан", "внуково", "домодедово", "шереметьево")
        ):
            return (
                "commercial airport terminal exterior and runway, aircraft on taxiway, "
                "wide aerial-style shot, no portraits"
            )
        if any(marker in lowered for marker in ("f-35", "истребител", "самолёт", "самолет", "авиа")):
            return (
                "a modern military fighter jet on a runway near northern coastline, "
                "overcast sky, distant horizon, no people"
            )
        if any(marker in lowered for marker in ("дрон", "бпла", "беспилот")):
            return "a military drone silhouette against a cloudy sky, dramatic light, no people"
        if any(marker in lowered for marker in ("спорт", "матч", "чемпион", "гол", "футбол", "хоккей")):
            return "dynamic sports action scene, stadium atmosphere, motion blur, no player names"
        if any(marker in lowered for marker in ("angular", "react", "github", "cli", "devtools")):
            return "minimal 3D tech icon on dark background, single object, studio light"
        if any(
            marker in lowered
            for marker in (
                "дорог", "трас", "автомобил", "автомоб", "дтп", "столкновен",
                "азс", "бензин", "заправ", "топлив", "парковк", "грузовик", "фура",
            )
        ):
            return (
                "cars and highway or gas station scene, editorial wide shot, "
                "vehicles and infrastructure only, no portraits"
            )
        if any(marker in lowered for marker in ("пожар", "горит", "возгоран")):
            return "firefighters extinguishing a blaze, smoke plume, wide shot from distance"
        if any(marker in lowered for marker in ("наводнен", "павод", "ураган", "шторм", "землетряс")):
            return "severe weather impact on city infrastructure, wide environmental shot, no portraits"
        if any(marker in lowered for marker in ("акци", "бирж", "мосбирж", "рубл", "инфляц", "эконом")):
            return (
                "stock market trading floor monitors and ticker boards, "
                "abstract financial charts as background lights, no people"
            )
        if any(marker in lowered for marker in ("ракет", "атак", "обстрел", "всу", "войн", "военн", "фронт")):
            return (
                "military equipment and smoke on distant horizon, documentary wide shot, "
                "no individual portraits"
            )
        return (
            "symbolic inanimate scene representing the news topic — relevant objects, "
            "vehicles, buildings or landscape, wide environmental shot, "
            "no people, no faces, no portraits"
        )

    @staticmethod
    def extract_tool_name(article_title: str, topic: str) -> str:
        """Извлекает короткое имя из заголовка."""
        title = article_title.strip()
        if not title:
            return topic.strip() or "topic"
        for separator in (":", "—", " – ", " - "):
            if separator in title:
                candidate = title.split(separator, 1)[0].strip()
                if candidate:
                    return candidate
        return title[:80]

    @staticmethod
    def _normalize_scene(draft_image_prompt: str, tool_name: str, topic: str) -> str:
        """Очищает описание сцены от абстрактных клише."""
        scene = draft_image_prompt.strip()
        if not scene:
            return f"a simple object symbolizing {ImagePromptBuilder._strip_cyrillic(tool_name) or topic}"

        lowered = scene.lower()
        abstract_markers = (
            "neural network",
            "holographic",
            "futuristic interface",
            "floating window",
            "matrix",
            "cyberpunk",
            "abstract tech",
            "нейросет",
            "голограм",
            "футуристич",
        )
        if any(marker in lowered for marker in abstract_markers):
            return f"a simple object symbolizing {ImagePromptBuilder._strip_cyrillic(tool_name) or topic}"

        scene = re.sub(
            r"\b(code snippets?|terminal (window|screen)|source code|ui screenshot)\b",
            "simple object",
            scene,
            flags=re.IGNORECASE,
        )
        return scene[:400]

    @staticmethod
    def _sanitize_scene_for_qwen(scene: str) -> str:
        """Убирает триггеры появления текста на картинке."""
        cleaned = scene.strip()
        if not cleaned:
            return "single symbolic object on neutral background"

        cleaned = re.sub(r"[а-яА-ЯёЁ]+", "", cleaned)
        text_triggers = (
            r"\b(with (text|words|caption|headline|title|label|writing|russian)|"
            r"russian text|cyrillic|"
            r"saying|labeled|inscription|typography|banner|poster|"
            r"magazine cover|book cover|newspaper headline|telegram|science-pop|audience)\b"
        )
        cleaned = re.sub(text_triggers, "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;")
        return cleaned or "single symbolic object on neutral background"
