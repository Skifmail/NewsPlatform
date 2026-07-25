"""Композитинг: реальный логотип репозитория поверх фиксированного фона.

В отличие от AI-генерации (Qwen), здесь фон никогда не меняется — он читается
с диска как есть на каждый вызов, и в него только вклеивается (alpha-композит)
подготовленный логотип. Так гарантируется «без изменения фона».
"""

from io import BytesIO
from pathlib import Path

import httpx
from loguru import logger
from PIL import Image, ImageDraw, ImageFilter

from app.infrastructure.media_store import save_media
from app.infrastructure.parsers.github_repo_logo import (
    GitHubRepoLogoFetcher,
    parse_github_repo,
)

_USER_AGENT = "Mozilla/5.0 (compatible; NewsPlatform/1.0)"
_FETCH_TIMEOUT = 20.0

BACKGROUND_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "assets"
    / "covers"
    / "github_findings_bg.png"
)

# Область на фоне, куда вписывается логотип (доли ширины/высоты холста).
# Первое приближение по превью фона — уточняется после того, как реальный
# файл ляжет на диск и появится тестовый композит с настоящим логотипом.
_SAFE_LEFT = 0.14
_SAFE_TOP = 0.15
_SAFE_RIGHT = 0.86
_SAFE_BOTTOM = 0.90
_SAFE_FILL_RATIO = 0.78  # логотип занимает не всю safe-область, а её часть


async def build_github_logo_cover(repo_url: str) -> str | None:
    """Собирает обложку: логотип репозитория на фиксированном фоне.

    Args:
        repo_url: ссылка на репозиторий GitHub.

    Returns:
        str | None: local:// ссылка на готовый JPEG или None при неудаче
        (нет логотипа / фон отсутствует / ошибка загрузки) — вызывающий код
        должен откатиться на прежний способ подбора обложки.
    """
    if not parse_github_repo(repo_url):
        return None
    if not BACKGROUND_PATH.exists():
        logger.warning(
            "Github findings background asset missing", path=str(BACKGROUND_PATH)
        )
        return None

    logo_url = await GitHubRepoLogoFetcher().fetch_logo_url(repo_url)
    if not logo_url:
        logger.debug("No logo found for repo, skip composite", repo_url=repo_url)
        return None

    logo = await _download_logo_image(logo_url)
    if logo is None:
        return None

    try:
        composed = _composite(BACKGROUND_PATH, logo)
    except Exception as exc:  # noqa: BLE001 — не должно ронять генерацию статьи
        logger.warning("Logo composite failed", repo_url=repo_url, error=str(exc))
        return None

    return save_media(composed, "covers", ".jpg")


async def _download_logo_image(url: str) -> Image.Image | None:
    """Скачивает логотип и растрирует его (SVG -> PNG) при необходимости.

    Args:
        url: URL логотипа (raster или SVG).

    Returns:
        Image.Image | None: RGBA-изображение логотипа.
    """
    try:
        async with httpx.AsyncClient(
            timeout=_FETCH_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
        content_type = resp.headers.get("content-type", "").lower()
        is_svg = "svg" in content_type or url.lower().split("?")[0].endswith(".svg")
        if is_svg:
            import cairosvg  # локальный импорт: нужен только для SVG-логотипов

            png_bytes = cairosvg.svg2png(bytestring=resp.content, output_width=800)
            return Image.open(BytesIO(png_bytes)).convert("RGBA")
        return Image.open(BytesIO(resp.content)).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Logo download/rasterize failed", url=url, error=str(exc))
        return None


def _composite(background_path: Path, logo: Image.Image) -> bytes:
    """Вклеивает логотип в safe-область фона, не меняя остальной фон.

    Args:
        background_path: путь к фиксированному фону (читается заново, не кэшируется).
        logo: логотип (RGBA).

    Returns:
        bytes: готовый JPEG.
    """
    background = Image.open(background_path).convert("RGBA")
    bg_w, bg_h = background.size
    x0, y0 = int(bg_w * _SAFE_LEFT), int(bg_h * _SAFE_TOP)
    x1, y1 = int(bg_w * _SAFE_RIGHT), int(bg_h * _SAFE_BOTTOM)
    safe_w, safe_h = x1 - x0, y1 - y0

    fitted = _fit_within(logo, int(safe_w * _SAFE_FILL_RATIO), int(safe_h * _SAFE_FILL_RATIO))
    content = _with_soft_shadow(fitted) if _has_real_transparency(fitted) else _with_card(fitted)

    layer = Image.new("RGBA", (safe_w, safe_h), (0, 0, 0, 0))
    paste_x = (safe_w - content.width) // 2
    paste_y = (safe_h - content.height) // 2
    layer.alpha_composite(content, (paste_x, paste_y))

    background.alpha_composite(layer, (x0, y0))
    buffer = BytesIO()
    background.convert("RGB").save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def _fit_within(img: Image.Image, max_w: int, max_h: int, max_upscale: float = 4.0) -> Image.Image:
    """Вписывает изображение в прямоугольник, сохраняя пропорции."""
    ratio = max(min(max_w / img.width, max_h / img.height, max_upscale), 0.01)
    new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def _has_real_transparency(img: Image.Image) -> bool:
    """True, если у изображения реально прозрачный (не полностью непрозрачный) фон."""
    if img.mode != "RGBA":
        return False
    alpha_min, _ = img.split()[-1].getextrema()
    return alpha_min < 250


def _with_soft_shadow(
    logo: Image.Image,
    blur: int = 16,
    offset: tuple[int, int] = (0, 14),
    opacity: int = 110,
) -> Image.Image:
    """Логотип с мягкой тенью — для логотипов с настоящей прозрачностью."""
    pad = blur * 3
    canvas = Image.new(
        "RGBA",
        (logo.width + pad * 2, logo.height + pad * 2 + abs(offset[1])),
        (0, 0, 0, 0),
    )
    shadow_alpha = logo.split()[-1].point(lambda a: min(a, opacity))
    shadow = Image.new("RGBA", logo.size, (0, 0, 0, 255))
    shadow.putalpha(shadow_alpha)
    canvas.alpha_composite(shadow, (pad + offset[0], pad + offset[1]))
    canvas = canvas.filter(ImageFilter.GaussianBlur(blur))
    canvas.alpha_composite(logo, (pad, pad))
    return canvas


def _with_card(logo: Image.Image, padding: int = 40, radius: int = 32) -> Image.Image:
    """Логотип на белой карточке с мягкой тенью — для непрозрачных логотипов."""
    card_w, card_h = logo.width + padding * 2, logo.height + padding * 2
    card = Image.new("RGBA", (card_w, card_h), (255, 255, 255, 255))
    mask = Image.new("L", (card_w, card_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, card_w - 1, card_h - 1), radius=radius, fill=255)
    card.putalpha(mask)
    card.paste(logo, (padding, padding), logo)
    return _with_soft_shadow(card, blur=20, offset=(0, 16), opacity=90)
