"""Тесты скоринга кандидатов на логотип репозитория."""

from app.infrastructure.parsers.github_repo_logo import GitHubRepoLogoFetcher


def _score(url: str, alt: str = "") -> int:
    return GitHubRepoLogoFetcher()._score_logo_candidate(url, alt)


def test_decorative_cover_without_logo_marker_rejected() -> None:
    """Баннер без слова logo/brand/icon в alt или пути не должен побеждать."""
    assert _score("https://cdn.example.com/github_cover_2.png", "") == 0


def test_decorative_banner_rejected_even_with_logo_alt() -> None:
    """Явный decorative-маркер в пути перевешивает случайное совпадение alt."""
    assert _score("https://example.com/social-preview-banner.png", "logo") < 90


def test_logo_png_accepted() -> None:
    assert _score("https://raw.githubusercontent.com/o/r/main/assets/logo.png", "") > 0


def test_logo_alt_text_accepted() -> None:
    assert _score("https://example.com/img/header.svg", "Project logo") > 0


def test_badge_url_rejected() -> None:
    assert _score("https://img.shields.io/badge/logo-blue.svg", "logo") == 0


def test_avatar_penalized_below_plain_logo() -> None:
    assert _score("https://example.com/logo-avatar.png", "") < _score(
        "https://example.com/logo.png", ""
    )
