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


def test_mark_does_not_match_inside_market() -> None:
    """Regression: substring-match ловил 'mark' внутри 'market' (sponsor logo)."""
    assert _score("https://example.com/images/sponsors/ss-market.png", "") == 0


def test_wordmark_still_matches_as_whole_token() -> None:
    assert _score("https://example.com/assets/wordmark.svg", "") > 0


def test_sponsor_logo_rejected_even_with_icon_marker() -> None:
    """Regression: спам-стена спонсоров (Swiper) — 'icon' в имени чужого файла
    не должен побеждать, путь sponsors/ — жёсткое исключение."""
    assert (
        _score(
            "https://swiperjs.com/images/sponsors/ai-text-humanizer-icon.png",
            "AI Text Humanizer",
        )
        == 0
    )
