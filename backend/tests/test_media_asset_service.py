"""Tests for media asset library registration."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.domain.enums import ImageSource
from app.infrastructure.models.processed_post import ProcessedPost
from app.services.media_asset_service import MediaAssetService


def test_should_keep_local_and_generated() -> None:
    assert MediaAssetService._should_keep("local://covers/a.png", ImageSource.ORIGINAL.value)
    assert MediaAssetService._should_keep(
        "https://cdn.example/x.png", ImageSource.GENERATED.value
    )
    assert not MediaAssetService._should_keep(
        "https://cdn.example/x.png", ImageSource.ORIGINAL.value
    )


@pytest.mark.asyncio
async def test_register_from_post_creates_cover_and_animation() -> None:
    post = ProcessedPost(
        id=42,
        channel_id=7,
        rewritten_text="teaser",
        article_title="Hello Cover",
        generated_image_url="local://covers/abc.png",
        generated_video_url="local://animations/abc.mp4",
        image_source=ImageSource.GENERATED.value,
        status="pending",
    )
    session = MagicMock()
    session.flush = AsyncMock()
    svc = MediaAssetService(session)
    svc._repo.get_by_storage_url = AsyncMock(return_value=None)
    created = []

    async def _create(asset):
        asset.id = len(created) + 1
        created.append(asset)
        return asset

    svc._repo.create = AsyncMock(side_effect=_create)

    assets = await svc.register_from_post(post)
    assert len(assets) == 2
    assert {a.kind for a in assets} == {"cover", "animation"}
    assert all(a.channel_id == 7 for a in assets)
    assert all(a.processed_post_id == 42 for a in assets)
    assert assets[0].title == "Hello Cover"


@pytest.mark.asyncio
async def test_register_skips_remote_originals() -> None:
    post = ProcessedPost(
        id=1,
        channel_id=1,
        rewritten_text="news",
        generated_image_url="https://news.example/photo.jpg",
        image_source=ImageSource.ORIGINAL.value,
        status="pending",
    )
    session = MagicMock()
    svc = MediaAssetService(session)
    svc._repo.get_by_storage_url = AsyncMock()
    svc._repo.create = AsyncMock()

    assets = await svc.register_from_post(post)
    assert assets == []
    svc._repo.create.assert_not_called()
