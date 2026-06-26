"""Тесты форматирования devtools-анонсов."""

from app.infrastructure.ai.devtools_teaser_formatter import (
    build_devtools_teaser,
    devtools_writing_instructions,
    extract_devtools_hook,
    is_banned_hook_opening,
    is_devtools_article_channel,
)


def test_is_devtools_article_channel() -> None:
    assert is_devtools_article_channel("it", "Github | Находки")
    assert not is_devtools_article_channel("news", "Github | Находки")


def test_extract_devtools_hook() -> None:
    teaser = "<b>pueue</b>\n\n🎬 Устали держать терминал открытым?\n\n🛠 <b>Что умеет:</b>"
    assert extract_devtools_hook(teaser) == "Устали держать терминал открытым?"


def test_is_banned_hook_opening() -> None:
    assert is_banned_hook_opening("Устали от облачных подписок?")
    assert is_banned_hook_opening("Замучились копировать дампы?")
    assert not is_banned_hook_opening("Cloudflare открыли Pingora на Rust")


def test_devtools_writing_instructions_includes_recent_hooks() -> None:
    text = devtools_writing_instructions(
        900,
        recent_hooks=["Передавайте файлы одной командой"],
    )
    assert "Устали от" in text
    assert "Передавайте файлы одной командой" in text
    assert "факт/новость" in text


def test_build_devtools_teaser() -> None:
    teaser = build_devtools_teaser(
        {
            "project_name": "croc",
            "hook": "Передача файлов одной командой с E2E-шифрованием.",
            "features": ["CLI", "кодовая фраза"],
            "insight": "Для быстрой пересылки без облака.",
            "language": "Go",
            "stars": "12k",
            "forks": "—",
            "repo_url": "https://github.com/schollz/croc",
        },
        teaser_max_length=900,
    )
    assert "<b>croc</b>" in teaser
    assert "🎬 Передача файлов" in teaser
    assert "GitHub" in teaser
