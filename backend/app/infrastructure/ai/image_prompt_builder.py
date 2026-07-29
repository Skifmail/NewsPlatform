"""Сборка промптов для генерации обложек.

Тексты промптов и негативов живут в БД (prompt_templates: image.*, negative.*)
и приходят сюда аргументами — модуль содержит только логику подстановки.
"""

import re

from loguru import logger

from app.infrastructure.models.channel import Channel
from app.utils.safe_format import safe_format


class ImagePromptBuilder:
    """Формирует промпты обложек только из настроек канала."""

    @staticmethod
    def writer_image_guidelines(
        channel: Channel,
        *,
        default_hint: str,
        postcard_hint: str,
        paragraph_hint: str,
    ) -> str:
        """Краткая инструкция для поля image_prompt в ArticleWriter.

        Args:
            channel: канал публикации.
            default_hint: инструкция по умолчанию (image.writer_hint_default).
            postcard_hint: инструкция для открыток (image.writer_hint_postcard).
            paragraph_hint: инструкция для «Параграф» (image.writer_hint_paragraph).

        Returns:
            str: инструкция для поля image_prompt.
        """
        name = (channel.name or "").lower()
        if "параграф" in name:
            return paragraph_hint
        if channel.topic == "postcard" or "открытк" in name:
            return postcard_hint
        return default_hint

    @staticmethod
    def build_logo_edit(
        channel: Channel,
        *,
        template: str,
        scene: str,
        tool_name: str = "",
    ) -> str:
        """Промпт стилизации найденного логотипа (отдельно от генерации с нуля).

        Args:
            channel: канал (для будущей кастомизации).
            template: шаблон с {scene} (image.logo_edit_template).
            scene: метафора работы инструмента (англ., от ArticleWriter).
            tool_name: имя инструмента.

        Returns:
            str: инструкция для Qwen Image Edit.
        """
        _ = channel, tool_name
        safe_scene = ImagePromptBuilder._sanitize_scene_for_qwen(scene) or (
            "how the tool works"
        )
        return safe_format(template, scene=safe_scene)

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
    def build_cover_prompt(
        *,
        template: str,
        article_title: str,
        draft_image_prompt: str,
        teaser: str = "",
    ) -> str:
        """Промпт журнальной обложки с заголовком для gpt-image-2.

        Текст редактируется в панели промптов (image.cover_prompt,
        переменные {title} и {summary}).
        НЕ вырезает кириллицу — gpt-image-2 умеет рендерить русский текст.

        Args:
            template: шаблон с {title} и {summary}.
            article_title: заголовок статьи.
            draft_image_prompt: описание сути статьи от ArticleWriter.
            teaser: анонс статьи (дополняет summary).

        Returns:
            str: промпт для генератора обложки.
        """
        title = article_title.strip()
        summary = draft_image_prompt.strip()
        if teaser:
            summary = f"{summary} {teaser.strip()}" if summary else teaser.strip()
        summary = summary[:800] if summary else title
        return safe_format(template, title=title, summary=summary)

    @staticmethod
    def build_postcard_cover_prompt(
        *,
        template: str,
        title: str,
        scene: str = "",
        greeting_text: str = "",
    ) -> str:
        """Собирает запрос к генератору открытки из шаблона панели промптов.

        Даже если шаблон в БД минимальный, добавляет немного арт-дирекшна:
        больше визуального разнообразия, меньше клише и отказ от неестественной
        надписи, если для неё нет качественного greeting_text.
        """
        title_text = title.strip()
        scene_text = scene.strip()
        greeting = greeting_text.strip()
        base_prompt = safe_format(
            template,
            title=title_text,
            scene=scene_text,
            greeting_text=greeting,
        ).strip()
        base_prompt = re.sub(r'^.*«».*(?:\n|$)', '', base_prompt, flags=re.MULTILINE)
        base_prompt = re.sub(r'^.*"".*(?:\n|$)', '', base_prompt, flags=re.MULTILINE)
        base_prompt = re.sub(r'^\s*Смысловой акцент:\s*(?:\n|$)', '', base_prompt, flags=re.MULTILINE)
        base_prompt = re.sub(r'\n{2,}', '\n', base_prompt).strip()

        extra_lines: list[str] = []
        if "1:1" not in base_prompt and "квадрат" not in base_prompt.lower():
            extra_lines.append(
                "Сделай квадратную открытку 1:1 с разнообразной композицией, а не шаблонный повтор прошлых сцен."
            )
        if "клише" not in base_prompt.lower():
            extra_lines.append(
                "Избегай визуальных клише вроде одинаковых голубей, чашек, цветов у окна и однотипных золотых надписей, если это не требуется по смыслу темы."
            )
        if "палитру" not in base_prompt.lower() and "ракурс" not in base_prompt.lower():
            extra_lines.append(
                "Подбери предметы, сезон, палитру, ракурс и свет под сам повод, чтобы открытки отличались друг от друга."
            )
        if scene_text and scene_text not in base_prompt:
            extra_lines.append(f"Смысловой визуальный акцент: {scene_text}.")
        if greeting:
            if greeting not in base_prompt:
                extra_lines.append(
                    f'Если добавляешь текст на открытку, используй только одну короткую естественную надпись: «{greeting}».'
                )
        elif "не добавляй текст" not in base_prompt.lower() and "без текста" not in base_prompt.lower():
            extra_lines.append(
                "Если короткая естественная надпись не получается, лучше оставь открытку без текста."
            )
        if not extra_lines:
            return base_prompt
        return "\n".join([base_prompt, *extra_lines]) if base_prompt else "\n".join(extra_lines)

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
        tech_markers = (
            "чип", "процессор", "смартфон", "телефон", "iphone", "айфон",
            "android", "андроид", "гаджет", "ноутбук", "планшет", "нейросет",
            "искусственн", "робот", "приложени", "видеокарт", "сервер", "облач",
            "браузер", "стартап", "кибер", "хакер", "взлом", "софт",
            "nvidia", "нвидиа", "apple", "эппл", "google", "гугл", "microsoft",
            "майкрософт", "samsung", "самсунг", "intel", "amd", "openai",
        )
        if any(marker in lowered for marker in tech_markers):
            return (
                "a sleek modern tech gadget or a glowing microchip on a dark "
                "reflective surface, single hero object, soft studio lighting, minimal"
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
