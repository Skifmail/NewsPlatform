"""Serve and upload media files from shared volume.

Callers: frontend ManualPublishView (POST /api/media/upload),
PublishService / ImageService (GET /api/media/{path}).
"""

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import AuthDep
from app.api.schemas.post import MediaUploadResponse
from app.infrastructure.media_store import MEDIA_ROOT, public_media_url, save_media

router = APIRouter(tags=["media"])

_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
_VIDEO_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
}
_MAX_UPLOAD_BYTES = 250 * 1024 * 1024  # 250 MB


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


@router.post("/media/upload", response_model=MediaUploadResponse)
async def upload_media_file(
    _: AuthDep,
    file: UploadFile = File(...),
) -> MediaUploadResponse:
    """Загружает изображение или видео для ручной публикации.

    Args:
        file: multipart-файл (image/* или video/*).

    Returns:
        MediaUploadResponse: local:// URL и публичный /api/media/... путь.

    Raises:
        HTTPException: неверный тип, пустой или слишком большой файл.
    """
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type in _IMAGE_TYPES:
        kind = "image"
        subdir = "manual/covers"
        suffix = _IMAGE_TYPES[content_type]
    elif content_type in _VIDEO_TYPES:
        kind = "video"
        subdir = "manual/videos"
        suffix = _VIDEO_TYPES[content_type]
    else:
        name = (file.filename or "").lower()
        if name.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
            kind = "image"
            subdir = "manual/covers"
            suffix = Path(name).suffix if name.endswith((".png", ".webp", ".gif")) else ".jpg"
            if suffix == ".jpeg":
                suffix = ".jpg"
        elif name.endswith((".mp4", ".webm", ".mov")):
            kind = "video"
            subdir = "manual/videos"
            suffix = Path(name).suffix
        else:
            raise HTTPException(
                status_code=400,
                detail="Поддерживаются изображения (JPEG/PNG/WebP/GIF) и видео (MP4/WebM/MOV)",
            )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой (макс. {_MAX_UPLOAD_BYTES // (1024 * 1024)} МБ)",
        )

    storage_url = save_media(data, subdir, suffix=suffix)
    return MediaUploadResponse(
        url=storage_url,
        public_url=public_media_url(storage_url) or storage_url,
        kind=kind,  # type: ignore[arg-type]
        filename=file.filename or f"upload{suffix}",
        size=len(data),
    )
