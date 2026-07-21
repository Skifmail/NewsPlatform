"""Форматирование Telegram-анонса для каналов devtools / GitHub-находок."""

import json
import re
from typing import Any

_GITHUB_RE = re.compile(r"https?://github\.com/[\w.-]+/[\w.-]+", re.IGNORECASE)


def is_devtools_article_channel(channel_topic: str, channel_name: str) -> bool:
    """Определяет, нужен ли формат карточки GitHub-находки.

    Args:
        channel_topic: тематика канала.
        channel_name: название канала.

    Returns:
        bool: True для IT-каналов с находками.
    """
    if channel_topic != "it":
        return False
    lowered = channel_name.lower()
    return any(marker in lowered for marker in ("github", "находк", "devtools", "dev tools"))


_HOOK_OPENING_BANS = (
    "устали от",
    "устали ",
    "устал от",
    "замучились",
    "надоело",
    "сколько можно",
    "каждый раз когда",
)


def devtools_writing_instructions(
    teaser_max_length: int,
    *,
    recent_hooks: list[str] | None = None,
) -> str:
    """Возвращает дополнительные инструкции для ArticleWriter (devtools).

    Args:
        teaser_max_length: лимит анонса в Telegram.
        recent_hooks: недавние крючки канала — модель не должна их повторять.

    Returns:
        str: блок инструкций на русском.
    """
    anti_repeat = ""
    if recent_hooks:
        samples = "\n".join(f"- {hook}" for hook in recent_hooks[:8])
        anti_repeat = f"""

Недавние крючки канала (НЕ копируй формулировки и не используй те же заходы):
{samples}"""

    return f"""Формат Telegram-анонса (поле teaser соберёт платформа — заполни структурные поля):

Ответь JSON с ключами:
title, body_html, image_prompt,
project_name, repo_url, language, stars, forks, hook, features, insight.

- project_name — короткое имя репозитория/утилиты (openscreen, mise, duckdb).
- repo_url — прямая ссылка на GitHub/GitLab (обязательно для превью в Telegram).
- language — основной язык (#TypeScript, Rust, Go…) — только из исследования.
- stars, forks — как на GitHub (3.1k, 174) — только если есть в исследовании, иначе «—».
- hook — 1–2 предложения: цепляющий вход в карточку, живо, без кликбейта.
  Чередуй форматы (каждый пост — другой тип захода):
  • факт/новость: «Cloudflare открыли свой прокси-фреймворк на Rust»
  • контраст: «Вместо awk/sed — таблицы и JSON из коробки»
  • вопрос: «Как передать файл без облака и регистрации?»
  • возможность: «Мониторинг CPU и стресс-тест в одном TUI»
  • сценарий: «Закоммитили ключ — инструмент найдёт его в истории Git»
  ЗАПРЕЩЕНО начинать hook с: «Устали от», «Устали», «Замучились», «Надоело» — это шаблон ИИ.
  Эмодзи в hook — не больше одного; платформа сама добавит 🎬 перед текстом.
- features — массив из 3–5 коротких пунктов «что умеет».
- insight — 1 предложение «кому зайдёт / в чём фишка» (💡).
- teaser — оставь пустой строкой "" (соберём автоматически).{anti_repeat}

body_html — основной текст для публикации в Telegram (не Telegraph): развёрнутый обзор.
Ориентир объёма body_html — поле max_length в основном промпте.

ВАЖНО (переопределяет структуру основного промпта для этого канала):
НЕ добавляй в конце body_html вопрос-вовлечение к читателю и эмодзи 👇
(«А вы готовы…?», «А вы пробовали…?» и т.п.). Заверши body_html содержательным
выводом и списком ссылок на источники — без вопроса и без призыва к действию."""


def extract_devtools_hook(teaser_html: str) -> str:
    """Извлекает текст крючка из собранного devtools-анонса.

    Args:
        teaser_html: HTML карточки (rewritten_text).

    Returns:
        str: текст hook без эмодзи 🎬 или пустая строка.
    """
    for line in teaser_html.splitlines():
        stripped = line.strip()
        if stripped.startswith("🎬"):
            return stripped.removeprefix("🎬").strip()
    return ""


def is_banned_hook_opening(hook: str) -> bool:
    """Проверяет, начинается ли крючок с заезженного шаблона.

    Args:
        hook: текст крючка.

    Returns:
        bool: True если заход в чёрном списке.
    """
    lowered = hook.strip().lower()
    return any(lowered.startswith(prefix) for prefix in _HOOK_OPENING_BANS)


def build_devtools_teaser(
    data: dict[str, Any],
    *,
    teaser_max_length: int,
    research_context: str = "",
) -> str:
    """Собирает HTML-анонс в стиле карточки GitHub-находки.

    Args:
        data: поля из ответа модели.
        teaser_max_length: лимит длины.
        research_context: текст исследования для fallback URL.

    Returns:
        str: HTML для Telegram.
    """
    project_name = str(data.get("project_name") or "").strip()
    if not project_name:
        project_name = _project_name_from_title(str(data.get("title", "")))

    repo_url = str(data.get("repo_url") or "").strip()
    if not repo_url:
        repo_url = extract_github_url(research_context)

    language = _normalize_language(str(data.get("language") or ""))
    stars = str(data.get("stars") or "—").strip() or "—"
    forks = str(data.get("forks") or "—").strip() or "—"
    hook = str(data.get("hook") or data.get("teaser") or "").strip()
    insight = str(data.get("insight") or "").strip()
    features = _normalize_features(data.get("features"))

    lines: list[str] = [f"<b>{project_name}</b>"]
    if hook:
        lines.append(f"\n🎬 {hook}")
    if features:
        lines.append("\n🛠 <b>Что умеет:</b>")
        lines.extend(f"• {item}" for item in features)
    if insight:
        lines.append(f"\n💡 {insight}")

    meta: list[str] = []
    if language and language != "—":
        meta.append(f"📁 #{language}")
    if stars != "—":
        meta.append(f"⭐ {stars}")
    if forks != "—":
        meta.append(f"Forks {forks}")
    if meta:
        lines.append("\n" + "\n".join(meta))

    if repo_url:
        lines.append(f'\n🔗 <a href="{repo_url}">GitHub</a>')

    teaser = "\n".join(lines).strip()
    if len(teaser) > teaser_max_length:
        teaser = f"{teaser[: teaser_max_length - 1].rstrip()}…"
    return teaser


def _project_name_from_title(title: str) -> str:
    """Извлекает имя проекта из заголовка статьи.

    Args:
        title: заголовок.

    Returns:
        str: имя проекта.
    """
    for separator in (":", "—", " – ", " - "):
        if separator in title:
            return title.split(separator, 1)[0].strip()
    return title.strip()[:80] or "tool"


def extract_github_url(text: str) -> str:
    """Ищет первую ссылку на репозиторий GitHub в тексте.

    Args:
        text: исследование или сниппеты.

    Returns:
        str: URL или пустая строка.
    """
    match = _GITHUB_RE.search(text)
    return match.group(0) if match else ""


def _normalize_language(raw: str) -> str:
    """Нормализует название языка для хештега.

    Args:
        raw: значение от модели.

    Returns:
        str: язык без # или «—».
    """
    cleaned = raw.strip().lstrip("#")
    if not cleaned or cleaned.lower() in {"unknown", "n/a", "—"}:
        return "—"
    return cleaned


def _normalize_features(raw: object) -> list[str]:
    """Приводит features к списку строк.

    Args:
        raw: массив или строка от модели.

    Returns:
        list[str]: пункты списка.
    """
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()][:5]
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()][:5]
        except json.JSONDecodeError:
            pass
        return [line.strip(" •\t-") for line in raw.split("\n") if line.strip()][:5]
    return []
