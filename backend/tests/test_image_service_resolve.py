"""Тесты выбора изображения новости (оригинал vs генерация)."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.domain.enums import ImageSource
from app.infrastructure.ai.image_service import ImageService, _is_raster_image_url


def test_is_raster_image_url() -> None:
    assert _is_raster_image_url("https://habrastorage.org/x/00859048")  # без расш.
    assert _is_raster_image_url("https://site.ru/img/photo.jpg")
    assert _is_raster_image_url("https://site.ru/img/photo.png?w=730")
    # SVG-заглушка cnews и документы — не растр.
    assert not _is_raster_image_url("https://filearchive.cnews.ru/a/path7204.svg")
    assert not _is_raster_image_url("https://site.ru/a/logo.SVG?v=2")
    assert not _is_raster_image_url("https://site.ru/doc.pdf")


@pytest.mark.asyncio
async def test_svg_original_routes_to_generation() -> None:
    """SVG-«оригинал» игнорируется → генерируем обложку."""
    svc = ImageService()
    svc._fetch_page_image = AsyncMock(return_value=None)
    svc._generate_for_post = AsyncMock(return_value="https://gen/cover.png")
    raw = SimpleNamespace(
        image_url="https://filearchive.cnews.ru/img/cnews/2021/02/03/path7204.svg",
        url="https://cnews.ru/news/x",
    )
    url, src = await svc.resolve_image(raw, SimpleNamespace(), generate_if_missing=True)
    assert (url, src) == ("https://gen/cover.png", ImageSource.GENERATED.value)
    svc._generate_for_post.assert_awaited_once()


@pytest.mark.asyncio
async def test_svg_original_without_generation_is_none() -> None:
    """Без разрешения на генерацию SVG-оригинал даёт NONE, а не битый URL."""
    svc = ImageService()
    svc._fetch_page_image = AsyncMock(return_value=None)
    raw = SimpleNamespace(
        image_url="https://filearchive.cnews.ru/a/path7204.svg", url=None
    )
    url, src = await svc.resolve_image(raw, SimpleNamespace(), generate_if_missing=False)
    assert (url, src) == (None, ImageSource.NONE.value)


@pytest.mark.asyncio
async def test_raster_original_used_as_is() -> None:
    """Годный jpeg-оригинал используется без генерации."""
    svc = ImageService()
    svc._generate_for_post = AsyncMock(return_value="SHOULD_NOT_BE_CALLED")
    raw = SimpleNamespace(
        image_url="https://habrastorage.org/getpro/habr/upload_files/008/59",
        url="https://habr.com/x",
    )
    url, src = await svc.resolve_image(raw, SimpleNamespace(), generate_if_missing=True)
    assert src == ImageSource.ORIGINAL.value
    assert url == raw.image_url
    svc._generate_for_post.assert_not_awaited()
