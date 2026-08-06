"""Роутер медиатеки — галерея сгенерированных изображений по каналам."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.api.deps import AuthDep, DbSession
from app.api.schemas.media_asset import MediaAssetBackfillResponse, MediaAssetResponse
from app.repositories.media_asset_repository import MediaAssetRepository
from app.services.media_asset_service import MediaAssetService

router = APIRouter(prefix="/media-assets", tags=["media-assets"])


@router.get("", response_model=list[MediaAssetResponse])
async def list_media_assets(
    session: DbSession,
    _: AuthDep,
    channel_id: int | None = Query(None),
    kind: str | None = Query(None, pattern="^(cover|animation)$"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[MediaAssetResponse]:
    """Список сохранённых обложек/анимаций, фильтр по каналу."""
    assets = await MediaAssetRepository(session).list_assets(
        channel_id=channel_id,
        kind=kind,
        limit=limit,
        offset=offset,
    )
    return [MediaAssetResponse.model_validate(a) for a in assets]


@router.post("/backfill", response_model=MediaAssetBackfillResponse)
async def backfill_media_assets(
    session: DbSession,
    _: AuthDep,
    limit: int = Query(500, ge=1, le=2000),
) -> MediaAssetBackfillResponse:
    """Импортирует медиа из существующих постов (одноразово после деплоя)."""
    imported = await MediaAssetService(session).backfill_from_posts(limit=limit)
    await session.commit()
    return MediaAssetBackfillResponse(imported=imported)


@router.get("/{asset_id}/download")
async def download_media_asset(
    asset_id: int,
    session: DbSession,
    _: AuthDep,
) -> Response:
    """Скачивание оригинала (local://) с Content-Disposition attachment."""
    asset = await MediaAssetRepository(session).get_by_id(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Media asset not found")
    payload = MediaAssetService.resolve_download_bytes(asset)
    if not payload:
        raise HTTPException(
            status_code=400,
            detail="Asset is a remote URL; open preview link instead",
        )
    data, filename = payload
    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.delete("/{asset_id}", status_code=204)
async def delete_media_asset(
    asset_id: int,
    session: DbSession,
    _: AuthDep,
    delete_file: bool = Query(True),
) -> None:
    """Удаляет запись медиатеки и файл с диска."""
    ok = await MediaAssetService(session).delete_asset(
        asset_id, delete_file=delete_file
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Media asset not found")
    await session.commit()
