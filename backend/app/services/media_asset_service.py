"""Сервис медиатеки: регистрация и бэкап сгенерированных изображений."""

from pathlib import Path

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import ImageSource
from app.infrastructure.media_store import (
    MEDIA_ROOT,
    is_local_media_url,
    read_media,
)
from app.infrastructure.models.media_asset import MediaAsset
from app.infrastructure.models.processed_post import ProcessedPost
from app.repositories.media_asset_repository import MediaAssetRepository


class MediaAssetService:
    """Регистрирует обложки/анимации в медиатеке по каналам."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = MediaAssetRepository(session)

    async def register_from_post(
        self,
        post: ProcessedPost,
        *,
        title: str | None = None,
    ) -> list[MediaAsset]:
        """Сохраняет обложку и анимацию поста в медиатеку.

        Регистрируются AI-сгенерированные URL и любые local:// файлы.
        Remote-оригиналы из источников новостей не копируются.

        Args:
            post: обработанный пост с image/video URL.
            title: подпись в галерее (заголовок статьи / превью).

        Returns:
            list[MediaAsset]: созданные или уже существующие записи.
        """
        label = title
        if not label:
            label = (post.article_title or post.rewritten_text or "")[:200] or None

        created: list[MediaAsset] = []
        if post.generated_image_url and self._should_keep(
            post.generated_image_url, post.image_source
        ):
            asset = await self._upsert(
                channel_id=post.channel_id,
                processed_post_id=post.id,
                kind="cover",
                image_source=post.image_source,
                storage_url=post.generated_image_url,
                title=label,
            )
            if asset:
                created.append(asset)

        if post.generated_video_url:
            asset = await self._upsert(
                channel_id=post.channel_id,
                processed_post_id=post.id,
                kind="animation",
                image_source=ImageSource.GENERATED.value,
                storage_url=post.generated_video_url,
                title=label,
            )
            if asset:
                created.append(asset)
        return created

    @staticmethod
    def _should_keep(url: str, image_source: str | None) -> bool:
        """Хранить AI-сгенерированные, ручные и уже локальные файлы."""
        if is_local_media_url(url):
            return True
        return image_source in (
            ImageSource.GENERATED.value,
            ImageSource.MANUAL.value,
        )

    async def _upsert(
        self,
        *,
        channel_id: int,
        processed_post_id: int | None,
        kind: str,
        image_source: str | None,
        storage_url: str,
        title: str | None,
    ) -> MediaAsset | None:
        """Создаёт ассет, если storage_url ещё не в медиатеке."""
        existing = await self._repo.get_by_storage_url(storage_url)
        if existing:
            if processed_post_id and existing.processed_post_id is None:
                existing.processed_post_id = processed_post_id
            if title and not existing.title:
                existing.title = title
            await self._session.flush()
            return existing

        asset = MediaAsset(
            channel_id=channel_id,
            processed_post_id=processed_post_id,
            kind=kind,
            image_source=image_source,
            storage_url=storage_url,
            title=title,
        )
        saved = await self._repo.create(asset)
        logger.info(
            "Media asset registered",
            asset_id=saved.id,
            channel_id=channel_id,
            kind=kind,
            storage_url=storage_url[:80],
        )
        return saved

    async def backfill_from_posts(self, *, limit: int = 500) -> int:
        """Импортирует медиа из существующих processed_posts в медиатеку.

        Args:
            limit: максимум постов за один проход.

        Returns:
            int: сколько новых записей создано.
        """
        result = await self._session.execute(
            select(ProcessedPost)
            .where(
                (ProcessedPost.generated_image_url.is_not(None))
                | (ProcessedPost.generated_video_url.is_not(None))
            )
            .order_by(ProcessedPost.id.desc())
            .limit(limit)
        )
        posts = list(result.scalars().all())
        added = 0
        for post in posts:
            label = (post.article_title or post.rewritten_text or "")[:200] or None
            candidates: list[tuple[str, str, str | None]] = []
            if post.generated_image_url and self._should_keep(
                post.generated_image_url, post.image_source
            ):
                candidates.append(
                    (post.generated_image_url, "cover", post.image_source)
                )
            if post.generated_video_url:
                candidates.append(
                    (
                        post.generated_video_url,
                        "animation",
                        ImageSource.GENERATED.value,
                    )
                )
            for storage_url, kind, source in candidates:
                if await self._repo.get_by_storage_url(storage_url):
                    continue
                await self._upsert(
                    channel_id=post.channel_id,
                    processed_post_id=post.id,
                    kind=kind,
                    image_source=source,
                    storage_url=storage_url,
                    title=label,
                )
                added += 1
        return added

    async def delete_asset(self, asset_id: int, *, delete_file: bool = True) -> bool:
        """Удаляет запись и опционально файл с volume.

        Args:
            asset_id: ID ассета.
            delete_file: удалить байты с диска для local://.

        Returns:
            bool: True если запись найдена и удалена.
        """
        asset = await self._repo.get_by_id(asset_id)
        if not asset:
            return False
        if delete_file and is_local_media_url(asset.storage_url):
            relative = asset.storage_url.removeprefix("local://")
            path = MEDIA_ROOT / relative
            try:
                resolved = path.resolve()
                if resolved.is_file() and resolved.is_relative_to(MEDIA_ROOT.resolve()):
                    path.unlink(missing_ok=True)
            except OSError as exc:
                logger.warning(
                    "Failed to delete media file", path=str(path), error=str(exc)
                )
        await self._repo.delete(asset)
        return True

    @staticmethod
    def resolve_download_bytes(asset: MediaAsset) -> tuple[bytes, str] | None:
        """Читает байты local:// ассета и имя файла для Content-Disposition.

        Returns:
            tuple[bytes, str] | None: (данные, filename) или None.
        """
        if not is_local_media_url(asset.storage_url):
            return None
        data = read_media(asset.storage_url)
        if data is None:
            return None
        relative = asset.storage_url.removeprefix("local://")
        filename = Path(relative).name or f"media-{asset.id}.bin"
        return data, filename
