"""Тесты сборки текста поста для VK."""

from types import SimpleNamespace

from app.infrastructure.publishers.vk_publisher import build_vk_message


def _post(article_body=None, rewritten_text=""):
    return SimpleNamespace(article_body=article_body, rewritten_text=rewritten_text)


def test_article_uses_full_body() -> None:
    """Для статьи берётся полный article_body, а не короткий анонс."""
    post = _post(
        article_body="<b>Заголовок</b>\n\nПолный текст статьи с <a href='u'>ссылкой</a>.",
        rewritten_text="короткий анонс",
    )
    msg = build_vk_message(post)
    assert "Полный текст статьи" in msg
    assert "короткий анонс" not in msg
    assert "<b>" not in msg and "<a" not in msg  # HTML вырезан


def test_news_uses_rewritten_text() -> None:
    post = _post(article_body=None, rewritten_text="<b>Новость</b> дня")
    msg = build_vk_message(post)
    assert "Новость дня" in msg
    assert "<b>" not in msg


def test_length_capped() -> None:
    post = _post(rewritten_text="a" * 20000)
    assert len(build_vk_message(post, limit=15000)) == 15000


def test_empty_post() -> None:
    assert build_vk_message(_post()) == ""
