"""Serve generated media files from shared volume."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.infrastructure.media_store import MEDIA_ROOT

router = APIRouter(tags=["media"])


@router.get("/media/{file_path:path}")
async def get_media_file(file_path: str) -> FileResponse:
    """Return a generated cover or animation for panel preview."""
    safe = Path(file_path)
    if safe.is_absolute() or ".." in safe.parts:
        raise HTTPException(status_code=400, detail="Invalid media path")
    full = (MEDIA_ROOT / safe).resolve()
    try:
        full.relative_to(MEDIA_ROOT.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid media path") from exc
    if not full.is_file():
        raise HTTPException(status_code=404, detail="Media not found")
    return FileResponse(full)
