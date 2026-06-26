"""Извлечение URL изображений из RSS и HTML."""

import re
from html import unescape
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

_SKIP_URL_PARTS = ("pixel", "spacer", "blank", "1x1", "avatar", "favicon", "logo-icon")
# Превью для соцсетей (og/share) — с заголовком и логотипом поверх фото
_SHARE_PREVIEW_MARKERS = (
    "/share_",
    "/share/",
    "_share.",
    "share_",
    "/og-image",
    "opengraph",
    "social-image",
    "social_image",
    "/preview_",
    "teaser_og",
)


def is_social_preview_image(url: str) -> bool:
    """Проверяет, что URL ведёт на картинку-превью для соцсетей, а не на фото в статье.

    Args:
        url: ссылка на изображение.

    Returns:
        bool: True если это share/og-превью (часто с текстом поверх).
    """
    lowered = url.lower()
    return any(marker in lowered for marker in _SHARE_PREVIEW_MARKERS)


def _is_usable_image_url(url: str | None, base_url: str | None = None) -> bool:
    """Проверяет, подходит ли URL для превью/публикации.

    Args:
        url: ссылка на картинку.
        base_url: базовый URL для относительных путей.

    Returns:
        bool: True если URL пригоден.
    """
    if not url or not str(url).strip():
        return False
    raw = str(url).strip()
    if raw.startswith("data:") or raw.startswith("telegram://"):
        return False
    lowered = raw.lower()
    if any(part in lowered for part in _SKIP_URL_PARTS):
        return False
    if not raw.startswith(("http://", "https://", "//")):
        if base_url:
            raw = urljoin(base_url, raw)
        else:
            return False
    if raw.startswith("//"):
        raw = f"https:{raw}"
    parsed = urlparse(raw)
    return bool(parsed.netloc and parsed.scheme in ("http", "https"))


def normalize_image_url(url: str, base_url: str | None = None) -> str | None:
    """Нормализует URL изображения.

    Args:
        url: исходная ссылка.
        base_url: база для относительных путей.

    Returns:
        str | None: абсолютный URL или None.
    """
    if not _is_usable_image_url(url, base_url):
        return None
    raw = str(url).strip()
    if raw.startswith("//"):
        return f"https:{raw}"
    if not raw.startswith(("http://", "https://")):
        return urljoin(base_url, raw) if base_url else None
    return raw


def _img_src_from_tag(img: object, base_url: str | None) -> str | None:
    """Достаёт src из тега img с учётом lazy-атрибутов.

    Args:
        img: тег BeautifulSoup.
        base_url: база для относительных путей.

    Returns:
        str | None: нормализованный URL.
    """
    for attr in ("src", "data-src", "data-original", "data-lazy-src", "srcset"):
        src = img.get(attr) if hasattr(img, "get") else None
        if not src:
            continue
        raw = str(src).split(",")[0].strip().split()[0]
        return normalize_image_url(raw, base_url)
    return None


def _pick_best_candidate(candidates: list[tuple[int, str]]) -> str | None:
    """Выбирает лучший URL по приоритету.

    Args:
        candidates: пары (приоритет, url).

    Returns:
        str | None: выбранный URL.
    """
    if not candidates:
        return None
    non_share = [(p, u) for p, u in candidates if not is_social_preview_image(u)]
    pool = non_share if non_share else candidates
    pool.sort(key=lambda item: item[0], reverse=True)
    return pool[0][1]


def extract_image_from_html(html: str, base_url: str | None = None) -> str | None:
    """Ищет фото в HTML: сначала img в тексте, og:image — только как запасной.

    Args:
        html: фрагмент HTML.
        base_url: база для относительных src.

    Returns:
        str | None: URL изображения.
    """
    if not html or len(html) < 10:
        return None
    soup = BeautifulSoup(unescape(html), "lxml")
    candidates: list[tuple[int, str]] = []

    article_selectors = (
        "[itemprop='articleBody'] img",
        ".topic-body__picture img",
        ".topic-body img",
        ".article__picture img",
        ".article-body img",
        ".post-content img",
        "article img",
        "figure img",
        ".picture img",
        ".box-photo img",
    )
    for selector in article_selectors:
        for img in soup.select(selector):
            found = _img_src_from_tag(img, base_url)
            if found:
                priority = 30 if not is_social_preview_image(found) else 5
                candidates.append((priority, found))

    for img in soup.find_all("img"):
        found = _img_src_from_tag(img, base_url)
        if found:
            priority = 20 if not is_social_preview_image(found) else 3
            candidates.append((priority, found))

    for selector, attr in (
        ('meta[property="og:image"]', "content"),
        ('meta[name="og:image"]', "content"),
        ('meta[property="og:image:url"]', "content"),
        ('meta[name="twitter:image"]', "content"),
        ('meta[property="twitter:image"]', "content"),
        ("link[rel='image_src']", "href"),
    ):
        tag = soup.select_one(selector)
        if tag and tag.get(attr):
            found = normalize_image_url(str(tag[attr]), base_url)
            if found:
                priority = 8 if not is_social_preview_image(found) else 1
                candidates.append((priority, found))

    return _pick_best_candidate(candidates)


def extract_image_from_rss_entry(entry: object, base_url: str | None = None) -> str | None:
    """Извлекает URL картинки из записи feedparser.

    Args:
        entry: элемент feedparser entries.
        base_url: ссылка на статью для относительных путей.

    Returns:
        str | None: URL изображения.
    """
    link = base_url
    if not link:
        link = getattr(entry, "link", None) or (
            entry.get("link") if isinstance(entry, dict) else None
        )

    def _get(key: str) -> object | None:
        if isinstance(entry, dict):
            return entry.get(key)
        return getattr(entry, key, None)

    candidates: list[tuple[int, str]] = []

    html_chunks: list[str] = []
    for key in ("summary", "description", "subtitle"):
        val = _get(key)
        if isinstance(val, str) and val:
            html_chunks.append(val)
    content = _get("content")
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("value"):
                html_chunks.append(str(part["value"]))

    for chunk in html_chunks:
        found = extract_image_from_html(chunk, link)
        if found:
            candidates.append((40, found))

    for chunk in html_chunks:
        match = re.search(
            r'https?://[^\s"\'<>]+\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'<>]*)?',
            chunk,
            re.I,
        )
        if match:
            found = normalize_image_url(match.group(0), link)
            if found:
                prio = 25 if not is_social_preview_image(found) else 2
                candidates.append((prio, found))

    if _get("media_content"):
        media = _get("media_content")
        if isinstance(media, list) and media:
            url = media[0].get("url") if isinstance(media[0], dict) else None
            found = normalize_image_url(str(url) if url else "", link)
            if found:
                prio = 15 if not is_social_preview_image(found) else 2
                candidates.append((prio, found))

    if _get("media_thumbnail"):
        thumbs = _get("media_thumbnail")
        if isinstance(thumbs, list) and thumbs:
            url = thumbs[0].get("url") if isinstance(thumbs[0], dict) else None
            found = normalize_image_url(str(url) if url else "", link)
            if found:
                prio = 12 if not is_social_preview_image(found) else 2
                candidates.append((prio, found))

    for enc in _get("enclosures") or []:
        if not isinstance(enc, dict):
            continue
        enc_type = str(enc.get("type", ""))
        if enc_type.startswith("image/"):
            href = enc.get("href") or enc.get("url")
            found = normalize_image_url(str(href) if href else "", link)
            if found:
                prio = 14 if not is_social_preview_image(found) else 2
                candidates.append((prio, found))

    for item in _get("links") or []:
        if not isinstance(item, dict):
            continue
        if str(item.get("type", "")).startswith("image/"):
            href = item.get("href")
            found = normalize_image_url(str(href) if href else "", link)
            if found:
                prio = 14 if not is_social_preview_image(found) else 2
                candidates.append((prio, found))

    image_field = _get("image")
    if isinstance(image_field, dict) and image_field.get("href"):
        found = normalize_image_url(str(image_field["href"]), link)
        if found:
            prio = 10 if not is_social_preview_image(found) else 1
            candidates.append((prio, found))

    return _pick_best_candidate(candidates)
