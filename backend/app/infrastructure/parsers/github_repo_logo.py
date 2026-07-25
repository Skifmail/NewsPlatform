"""Поиск логотипа open-source проекта на GitHub."""

import re

import httpx
from loguru import logger

_REPO_PATH_RE = re.compile(r"github\.com/([^/]+)/([^/#?]+)", re.IGNORECASE)
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_HTML_IMG_RE = re.compile(
    r'<img[^>]+src=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_BADGE_MARKERS = (
    "shields.io",
    "img.shields",
    "badge",
    "travis-ci",
    "circleci",
    "codecov",
    "snapcraft",
    "workflow",
    "/actions/",
    "contributors",
    "downloads",
    "stars?style",
    "fork?style",
    "gitpod",
    "vercel.app/badge",
)
_LOGO_MARKERS = ("logo", "brand", "wordmark", "icon", "emblem", "mark")
# Декоративные hero/social-preview картинки из README иногда лежат рядом с
# логотипом и проходят по расширению, но логотипом не являются — Excalidraw
# и подобные репозитории кладут такой баннер прямо в начало README.
_DECORATIVE_MARKERS = (
    "cover",
    "banner",
    "hero",
    "social",
    "preview",
    "showcase",
    "share",
)
_LOGO_MARKER_SET = frozenset(_LOGO_MARKERS)
_DECORATIVE_MARKER_SET = frozenset(_DECORATIVE_MARKERS)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> frozenset[str]:
    """Разбивает строку на словарные токены (для точного, не substring, matching)."""
    return frozenset(_TOKEN_RE.findall(text))
_RASTER_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".gif")

_USER_AGENT = "Mozilla/5.0 (compatible; NewsPlatform/1.0)"
_API_TIMEOUT = 20.0


def parse_github_repo(repo_url: str) -> tuple[str, str] | None:
    """Извлекает owner и имя репозитория из URL GitHub.

    Args:
        repo_url: ссылка на репозиторий.

    Returns:
        tuple[str, str] | None: (owner, repo) или None.
    """
    match = _REPO_PATH_RE.search(repo_url.strip())
    if not match:
        return None
    owner = match.group(1).strip()
    repo = match.group(2).removesuffix(".git").strip()
    if not owner or not repo:
        return None
    return owner, repo


class GitHubRepoLogoFetcher:
    """Находит URL логотипа проекта в README или типовых путях репозитория."""

    async def fetch_logo_url(self, repo_url: str) -> str | None:
        """Возвращает публичный URL логотипа репозитория.

        Args:
            repo_url: ссылка вида https://github.com/owner/repo.

        Returns:
            str | None: URL растрового изображения или None.
        """
        parsed = parse_github_repo(repo_url)
        if not parsed:
            return None
        owner, repo = parsed

        readme = await self._fetch_readme(owner, repo)
        if readme:
            logo = self._pick_best_logo_candidate(
                self._collect_markdown_images(readme, owner, repo)
            )
            if logo:
                logger.info(
                    "GitHub logo found in README",
                    owner=owner,
                    repo=repo,
                    url=logo,
                )
                return logo

        default_branch = await self._fetch_default_branch(owner, repo)
        if default_branch:
            for path in (
                "logo.png",
                "logo.jpg",
                "assets/logo.png",
                "docs/logo.png",
                f"docs/img/{repo}.png",
                f"img/{repo}.png",
            ):
                candidate = (
                    f"https://raw.githubusercontent.com/{owner}/{repo}/"
                    f"{default_branch}/{path}"
                )
                if await self._url_is_raster_image(candidate):
                    logger.info(
                        "GitHub logo found by static path",
                        owner=owner,
                        repo=repo,
                        url=candidate,
                    )
                    return candidate

        logger.debug("GitHub logo not found", owner=owner, repo=repo)
        return None

    async def _fetch_readme(self, owner: str, repo: str) -> str | None:
        """Скачивает README репозитория через GitHub API.

        Args:
            owner: владелец репозитория.
            repo: имя репозитория.

        Returns:
            str | None: текст README.
        """
        api_url = f"https://api.github.com/repos/{owner}/{repo}/readme"
        try:
            async with httpx.AsyncClient(
                timeout=_API_TIMEOUT,
                follow_redirects=True,
                headers={
                    "User-Agent": _USER_AGENT,
                    "Accept": "application/vnd.github.raw",
                },
            ) as client:
                response = await client.get(api_url)
                if response.status_code != 200:
                    return None
                text = response.text.strip()
                return text or None
        except Exception as exc:
            logger.debug(
                "GitHub README fetch failed",
                owner=owner,
                repo=repo,
                error=str(exc),
            )
            return None

    async def _fetch_default_branch(self, owner: str, repo: str) -> str | None:
        """Возвращает ветку по умолчанию репозитория.

        Args:
            owner: владелец.
            repo: имя репозитория.

        Returns:
            str | None: имя ветки.
        """
        api_url = f"https://api.github.com/repos/{owner}/{repo}"
        try:
            async with httpx.AsyncClient(
                timeout=_API_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = await client.get(api_url)
                if response.status_code != 200:
                    return "main"
                data = response.json()
                branch = str(data.get("default_branch", "")).strip()
                return branch or "main"
        except Exception:
            return "main"

    def _collect_markdown_images(
        self,
        readme: str,
        owner: str,
        repo: str,
    ) -> list[tuple[int, str]]:
        """Собирает кандидатов на логотип из README.

        Args:
            readme: markdown README.
            owner: владелец репозитория.
            repo: имя репозитория.

        Returns:
            list[tuple[int, str]]: пары (score, url).
        """
        candidates: list[tuple[int, str]] = []
        for alt, raw_url in _MD_IMAGE_RE.findall(readme):
            resolved = self._resolve_readme_image_url(raw_url.strip(), owner, repo)
            if not resolved:
                continue
            score = self._score_logo_candidate(resolved, alt)
            if score > 0:
                candidates.append((score, resolved))

        for raw_url in _HTML_IMG_RE.findall(readme):
            resolved = self._resolve_readme_image_url(raw_url.strip(), owner, repo)
            if not resolved:
                continue
            score = self._score_logo_candidate(resolved, "")
            if score > 0:
                candidates.append((score, resolved))

        return candidates

    @staticmethod
    def _pick_best_logo_candidate(candidates: list[tuple[int, str]]) -> str | None:
        """Выбирает лучший URL логотипа по score.

        Args:
            candidates: список (score, url).

        Returns:
            str | None: URL логотипа.
        """
        if not candidates:
            return None
        raster = [
            (score, url)
            for score, url in candidates
            if url.lower().split("?", 1)[0].endswith(_RASTER_SUFFIXES)
        ]
        pool = raster if raster else candidates
        pool.sort(key=lambda item: item[0], reverse=True)
        return pool[0][1]

    def _resolve_readme_image_url(
        self,
        raw_url: str,
        owner: str,
        repo: str,
    ) -> str | None:
        """Превращает относительный путь из README в абсолютный URL.

        Args:
            raw_url: ссылка из markdown.
            owner: владелец.
            repo: репозиторий.

        Returns:
            str | None: абсолютный URL.
        """
        if not raw_url or raw_url.startswith("data:"):
            return None
        cleaned = raw_url.strip().strip('"').strip("'")
        if cleaned.startswith("//"):
            cleaned = f"https:{cleaned}"
        if cleaned.startswith(("http://", "https://")):
            return cleaned if self._looks_like_image_url(cleaned) else None
        branch = "main"
        path = cleaned.lstrip("./")
        return (
            f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{path}"
        )

    @staticmethod
    def _looks_like_image_url(url: str) -> bool:
        """Проверяет, что URL похож на картинку.

        Args:
            url: ссылка.

        Returns:
            bool: True для png/jpg/webp/gif/svg.
        """
        lowered = url.lower().split("?", 1)[0]
        return lowered.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"))

    @staticmethod
    def _is_badge_url(url: str) -> bool:
        """Отсекает бейджи CI, stars shields и прочий шум.

        Args:
            url: ссылка на изображение.

        Returns:
            bool: True если это бейдж, а не логотип.
        """
        lowered = f"{url.lower()}"
        return any(marker in lowered for marker in _BADGE_MARKERS)

    def _score_logo_candidate(self, url: str, alt: str) -> int:
        """Оценивает, насколько URL похож на логотип проекта.

        Args:
            url: ссылка на изображение.
            alt: alt-текст из markdown.

        Returns:
            int: score; 0 — не подходит.
        """
        if self._is_badge_url(url):
            return 0
        lowered_url = url.lower()
        lowered_alt = alt.lower()
        # Токены по словам, а не substring: иначе "mark" (для wordmark)
        # ложно совпадает внутри "market", "denmark", "bookmark" и т.п.
        tokens = _tokenize(lowered_url) | _tokenize(lowered_alt)
        # Без явного сигнала «это логотип» не угадываем — иначе первая же
        # декоративная картинка в README (обложка, скриншот) выигрывает по
        # умолчанию просто потому, что больше нечего сравнивать.
        if not tokens & _LOGO_MARKER_SET:
            return 0
        score = 90
        if lowered_url.endswith(_RASTER_SUFFIXES):
            score += 20
        if lowered_url.endswith(".svg"):
            score += 5
        if "avatar" in lowered_url or "profile" in lowered_url:
            score -= 40
        if "screenshot" in lowered_url or "demo" in lowered_url:
            score -= 30
        if tokens & _DECORATIVE_MARKER_SET:
            score -= 70
        return max(score, 0)

    async def _url_is_raster_image(self, url: str) -> bool:
        """Проверяет HEAD-запросом, что URL отдаёт растровое изображение.

        Args:
            url: ссылка.

        Returns:
            bool: True если content-type image/* и не svg.
        """
        try:
            async with httpx.AsyncClient(
                timeout=_API_TIMEOUT,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT},
            ) as client:
                response = await client.head(url)
                if response.status_code >= 400:
                    response = await client.get(url)
                if response.status_code >= 400:
                    return False
                content_type = response.headers.get("content-type", "").lower()
                if not content_type.startswith("image/"):
                    return False
                return "svg" not in content_type
        except Exception:
            return False
