"""Детерминированное наложение короткого заголовка на обложку Параграфа."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from loguru import logger
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from app.infrastructure.media_store import save_media

# Системные шрифты с кириллицей (Debian/Ubuntu).
_FONT_CANDIDATES = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
)

_PARAGRAPH_MARK = "§"
_MAX_COVER_WORDS = 6


def overlay_cover_title(
    image_bytes: bytes,
    cover_title: str,
    *,
    mark: str = _PARAGRAPH_MARK,
) -> bytes | None:
    """Накладывает короткий заголовок и знак § на изображение без AI-текста.

    Args:
        image_bytes: исходный JPEG/PNG.
        cover_title: 2–5 слов для обложки.
        mark: маленький бренд-знак.

    Returns:
        bytes | None: JPEG с текстом или None при ошибке.
    """
    title = _normalize_cover_title(cover_title)
    if not title:
        return None
    try:
        image = Image.open(BytesIO(image_bytes)).convert("RGBA")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cover overlay: cannot open image", error=str(exc))
        return None

    width, height = image.size
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Затемнение нижней трети для контраста.
    gradient_top = int(height * 0.55)
    for y in range(gradient_top, height):
        alpha = int(170 * ((y - gradient_top) / max(1, height - gradient_top)))
        draw.line([(0, y), (width, y)], fill=(0, 0, 0, alpha))

    font = _load_font(size=max(36, width // 18))
    mark_font = _load_font(size=max(22, width // 36))
    lines = _wrap_text(title, font, max_width=int(width * 0.86), draw=draw)

    line_heights = [draw.textbbox((0, 0), line, font=font)[3] for line in lines]
    block_height = sum(line_heights) + 12 * (len(lines) - 1)
    y = height - int(height * 0.08) - block_height

    for line, line_h in zip(lines, line_heights, strict=True):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        draw.text((x + 2, y + 2), line, font=font, fill=(0, 0, 0, 180))
        draw.text((x, y), line, font=font, fill=(255, 255, 255, 245))
        y += line_h + 12

    if mark:
        mb = draw.textbbox((0, 0), mark, font=mark_font)
        mx = width - (mb[2] - mb[0]) - int(width * 0.04)
        my = int(height * 0.04)
        draw.text((mx + 1, my + 1), mark, font=mark_font, fill=(0, 0, 0, 160))
        draw.text((mx, my), mark, font=mark_font, fill=(255, 255, 255, 220))

    composed = Image.alpha_composite(image, overlay).convert("RGB")
    composed = composed.filter(
        ImageFilter.UnsharpMask(radius=1.2, percent=80, threshold=2)
    )
    buffer = BytesIO()
    composed.save(buffer, format="JPEG", quality=92, optimize=True)
    return buffer.getvalue()


def overlay_and_store(
    image_bytes: bytes,
    cover_title: str,
) -> str | None:
    """Накладывает заголовок и сохраняет на media volume.

    Args:
        image_bytes: исходное изображение.
        cover_title: текст обложки.

    Returns:
        str | None: local:// URL или None.
    """
    result = overlay_cover_title(image_bytes, cover_title)
    if not result:
        return None
    return save_media(result, "covers", ".jpg")


def _normalize_cover_title(raw: str) -> str:
    """Нормализует заголовок обложки: верхний регистр, лимит слов."""
    words = [w for w in raw.replace("—", " ").replace(":", " ").split() if w]
    short = " ".join(words[:_MAX_COVER_WORDS]).strip(" .,-«»\"'")
    return short.upper()


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Загружает шрифт с кириллицей."""
    for path in _FONT_CANDIDATES:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    logger.warning("Cover overlay: no TTF font found, using default")
    return ImageFont.load_default()


def _wrap_text(
    text: str,
    font: ImageFont.ImageFont,
    *,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> list[str]:
    """Переносит текст по словам под ширину холста."""
    words = text.split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:3]
