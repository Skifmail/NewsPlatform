"""Подготовка, личное согласование и однократная отправка дополнительных постов."""

import hashlib
import json
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Final, cast

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.supplements import (
    MOSCOW,
    PAIR_TTL_MINUTES,
    STALE_MINUTES,
    DeliveryUncertain,
    SupplementError,
    due_kind,
    validate_decision,
    validate_text,
)
from app.infrastructure.ai.image_service import ImageGenPrompts, ImageService
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.processed_post import ProcessedPost
from app.infrastructure.models.publish_log import PublishLog
from app.infrastructure.models.supplement import SupplementConfig, SupplementDraft
from app.infrastructure.publishers.max_review_client import MaxReviewClient
from app.infrastructure.search.tavily_client import TavilySearchResult
from app.repositories.setting_repository import SettingRepository
from app.repositories.supplement_repository import SupplementRepository
from app.services.media_asset_service import MediaAssetService
from app.services.platform_settings_service import PlatformSettingsService
from app.services.prompt_service import PromptService
from app.services.supplement_generator import SupplementGenerator, _fresh

_TOKEN_BYTES: Final = 32
_EDITABLE: Final = frozenset(
    {"review_pending", "awaiting", "delivery_failed", "delivery_unknown", "rejected"}
)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def publication_text(draft: SupplementDraft) -> str:
    """Возвращает текст, который увидит читатель.

    Args:
        draft: Черновик. Источники остаются в карточке редактора и не входят в текст.

    Returns:
        Обычный текст без списка ссылок и служебных подписей.
    """
    return draft.text


class SupplementService:
    """Управляет переходами состояний через блокировки и сохранённые задания.

    Attributes:
        repo: Репозиторий атомарных изменений.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        image_service: ImageService | None = None,
    ) -> None:
        """Подключает сессию и существующий бот.

        Args:
            session: Сессия БД.
            image_service: Сервис обложек или тестовая замена.
        """
        self._session = session
        self.repo = SupplementRepository(session)
        self._max = MaxReviewClient()
        self._images = image_service

    async def _image_service(self) -> ImageService:
        if self._images is not None:
            return self._images
        prompts = PromptService(self._session)
        image_prompts = ImageGenPrompts(
            no_text_negative=await prompts.get("negative.qwen_no_text"),
            news_negative=await prompts.get("negative.qwen_news"),
            cover_template=await prompts.get("image.cover_prompt"),
            postcard_cover_template=await prompts.get("image.cover_prompt_postcard"),
        )
        merged = await PlatformSettingsService(self._session).get_merged()
        self._images = ImageService.from_settings_dict(
            merged,
            prompts=image_prompts,
        )
        return self._images

    async def _set_progress(
        self,
        draft: SupplementDraft,
        stage: str,
        percent: int,
        detail: str,
    ) -> None:
        draft.progress_stage = stage
        draft.progress_percent = max(draft.progress_percent, min(percent, 100))
        draft.progress_detail = detail[:255]
        draft.progress_updated_at = datetime.now(UTC)
        await self._session.commit()

    async def _generate_image(
        self,
        draft: SupplementDraft,
        channel: Channel,
        image_prompt: str,
    ) -> tuple[str, str]:
        images = await self._image_service()
        image_url, image_source = await images.resolve_article_image(
            channel=channel,
            article_title=draft.title,
            topic=channel.topic,
            image_prompt=image_prompt,
            teaser=draft.text,
        )
        if not image_url or image_source == "none":
            raise SupplementError(
                "OpenAI не создал обложку; материал не отправлен на согласование"
            )
        return image_url, image_source

    async def _image_bytes(self, draft: SupplementDraft) -> bytes:
        if not draft.image_url:
            raise SupplementError(
                "У этой версии нет обложки; подготовьте материал заново"
            )
        result = await (await self._image_service()).download_and_resize(
            draft.image_url
        )
        if not result:
            raise SupplementError(
                "Сохранённая обложка недоступна; подготовьте материал заново"
            )
        return cast(bytes, result)

    async def reserve(
        self,
        channel_id: int,
        *,
        manual_kind: str | None = None,
        now: datetime | None = None,
    ) -> int | None:
        """Резервирует уникальный слот, не затрагивая утренние статьи.

        Args:
            channel_id: Канал.
            manual_kind: Ручная подготовка вместо расписания.
            now: Текущее время, подменяемое в тестах.

        Returns:
            Идентификатор задания или None, если слот не наступил/уже занят.

        Raises:
            SupplementError: Не настроено согласование или канал неактивен.
        """
        now = now or datetime.now(UTC)
        config = await self.repo.config(channel_id)
        channel = await self._session.get(Channel, channel_id)
        if channel is None or not channel.is_active:
            raise SupplementError("Канал выключен")
        if config.recipient_id is None:
            raise SupplementError("Сначала подключите редактора через MAX")
        if manual_kind is not None and manual_kind not in {"fact", "news"}:
            raise SupplementError("Неизвестный формат")
        kind = manual_kind or (
            due_kind(now, config.clock, config.fact_days, config.news_day)
            if config.enabled
            else None
        )
        if kind is None:
            await self._session.commit()
            return None
        slot = (
            f"manual:{secrets.token_hex(8)}"
            if manual_kind
            else now.astimezone(MOSCOW).date().isoformat()
        )
        existing = await self._session.scalar(
            select(SupplementDraft.id).where(
                SupplementDraft.channel_id == channel_id,
                SupplementDraft.slot_key == slot,
            )
        )
        if existing is not None:
            await self._session.commit()
            return None
        draft = SupplementDraft(
            channel_id=channel_id,
            slot_key=slot,
            requested_kind=kind,
            kind=kind,
            target_chat_id=channel.platform_id,
            progress_stage="queued",
            progress_percent=5,
            progress_detail="Задание ожидает запуска",
            progress_updated_at=datetime.now(UTC),
            trace={
                "rules": config.rules,
                "fact_rules": config.fact_rules,
                "news_rules": config.news_rules,
                "channel_name": channel.name,
                "configured_platform_id": channel.platform_id,
            },
        )
        self._session.add(draft)
        await self._session.commit()
        logger.info(
            "Дополнительный материал поставлен на подготовку",
            draft_id=draft.id,
            channel_id=channel_id,
            kind=kind,
        )
        return cast(int, draft.id)

    async def generate(self, draft_id: int) -> None:
        """Подготавливает сохранённое задание без отправки в канал.

        Args:
            draft_id: Черновик в состоянии queued.

        Raises:
            SupplementError: Черновик отсутствует.
        """
        draft = await self.repo.draft(draft_id)
        if draft.status != "queued":
            await self._session.commit()
            return
        draft.status = "generating"
        snapshot = dict(draft.trace)
        channel = await self._session.get(Channel, draft.channel_id)
        if channel is None:
            raise SupplementError("Канал не найден")
        await self._set_progress(
            draft,
            "planning",
            10,
            "Запускаем подготовку и читаем редакционные правила",
        )
        try:
            if snapshot.get("regenerate_image_only") is True:
                if not draft.image_prompt:
                    raise SupplementError(
                        "Нет описания обложки; перегенерируйте весь материал"
                    )
                await self._set_progress(
                    draft,
                    "image",
                    72,
                    "Создаём новую обложку OpenAI для исправленного текста",
                )
                image_url, image_source = await self._generate_image(
                    draft,
                    channel,
                    draft.image_prompt,
                )
                draft.image_url = image_url
                draft.image_source = image_source
                draft.trace = {
                    key: value
                    for key, value in snapshot.items()
                    if key != "regenerate_image_only"
                }
            else:
                history = await self.repo.history(draft.channel_id, draft.id)
                settings = SettingRepository(self._session)
                search_settings = {
                    "keys_raw": await settings.get("tavily_api_keys", "[]"),
                    "active_key_id": await settings.get("tavily_active_key_id", ""),
                    "auto_switch": (
                        await settings.get("tavily_auto_switch", "true")
                    ).lower()
                    == "true",
                }
                result = await SupplementGenerator().generate(
                    draft.requested_kind,
                    str(snapshot["rules"]),
                    history,
                    search_settings,
                    datetime.now(UTC),
                    fact_rules=str(snapshot["fact_rules"]),
                    news_rules=str(snapshot["news_rules"]),
                    progress=lambda stage, percent, detail: self._set_progress(
                        draft, stage, percent, detail
                    ),
                )
                draft.kind = result["kind"]
                draft.title = result["title"]
                draft.text = result["text"]
                draft.sources = result["sources"]
                draft.image_prompt = result["image_prompt"]
                draft.trace = {**snapshot, **result["trace"]}
                await self._set_progress(
                    draft,
                    "image",
                    72,
                    "Текст готов — создаём уникальную обложку через OpenAI",
                )
                draft.image_url, draft.image_source = await self._generate_image(
                    draft,
                    channel,
                    draft.image_prompt,
                )
        except (SupplementError, RuntimeError, ValueError, TypeError, KeyError) as exc:
            draft.status = "generation_failed"
            draft.error = (
                str(exc)
                if isinstance(exc, SupplementError)
                else "Не удалось создать обязательную обложку материала"
            )
            draft.progress_stage = "failed"
            draft.progress_detail = "Подготовка остановлена из-за ошибки"
            draft.progress_updated_at = datetime.now(UTC)
            await self._session.commit()
            logger.warning(
                "Подготовка дополнительного материала не завершена",
                draft_id=draft_id,
                reason=str(exc),
            )
            return
        draft.status = "review_pending"
        draft.error = None
        await self._set_progress(
            draft,
            "ready_for_delivery",
            88,
            "Текст и обложка готовы — готовим карточку для MAX",
        )

    async def deliver(self, draft_id: int) -> None:
        """Отправляет карточку редактору, фиксируя неопределённые результаты.

        Args:
            draft_id: Черновик для согласования.

        Raises:
            SupplementError: Черновик или конфигурация отсутствуют.
        """
        draft = await self.repo.draft(draft_id)
        if draft.status != "review_pending":
            await self._session.commit()
            return
        config = await self.repo.config(draft.channel_id)
        if config.recipient_id is None:
            draft.status, draft.error = "delivery_failed", "Редактор не подключён"
            await self._session.commit()
            return
        recipient = config.recipient_id
        try:
            image_bytes = await self._image_bytes(draft)
        except SupplementError as exc:
            draft.status, draft.error = "delivery_failed", str(exc)
            await self._session.commit()
            return
        draft.status = "delivering"
        await self._set_progress(
            draft,
            "delivering",
            94,
            "Отправляем текст, обложку и кнопки одобрения в MAX",
        )
        label = "Короткий факт" if draft.kind == "fact" else "Научная новость"
        fallback = str(draft.trace.get("fallback_reason") or "")
        text = (
            f"{label} · {draft.trace.get('channel_name', 'Канал')}\n"
            "Одобрение отправит текст ниже в канал сразу.\n\n"
            f"{publication_text(draft)}"
        )
        if fallback:
            text += f"\n\nЗамена новости фактом: {fallback}"
        buttons = [
            [
                {
                    "type": "callback",
                    "text": "Одобрить",
                    "payload": f"extra:{draft.id}:{draft.revision}:approve",
                },
                {
                    "type": "callback",
                    "text": "Отклонить",
                    "payload": f"extra:{draft.id}:{draft.revision}:reject",
                },
            ]
        ]
        try:
            if not re.fullmatch(r"-?\d+", draft.target_chat_id):
                draft.target_chat_id = await self._max.resolve_chat_id(
                    draft.target_chat_id
                )
                await self._session.commit()
            result = await self._max.send(
                text,
                user_id=recipient,
                buttons=buttons,
                image_bytes=image_bytes,
            )
            draft.review_mid = result["mid"]
            draft.status = "awaiting"
            draft.error = None
            draft.progress_stage = "awaiting_approval"
            draft.progress_percent = 100
            draft.progress_detail = "Материал доставлен и ждёт вашего решения в MAX"
            draft.progress_updated_at = datetime.now(UTC)
        except DeliveryUncertain as exc:
            draft.status, draft.error = "delivery_unknown", str(exc)
        except SupplementError as exc:
            draft.status, draft.error = "delivery_failed", str(exc)
        await self._session.commit()

    async def decide(
        self, draft_id: int, revision: int, user_id: int, message_id: str, action: str
    ) -> str:
        """Сохраняет решение владельца; отправка выполняется отдельной задачей.

        Args:
            draft_id: Черновик из кнопки.
            revision: Версия из кнопки.
            user_id: Автор нажатия.
            message_id: Сообщение согласования.
            action: approve или reject.

        Returns:
            Новое состояние.

        Raises:
            SupplementError: Решение не разрешено или новость устарела.
        """
        draft = await self.repo.draft(draft_id)
        config = await self.repo.config(draft.channel_id)
        validate_decision(
            draft.status,
            user_id,
            config.recipient_id,
            revision,
            draft.revision,
            message_id,
            draft.review_mid,
        )
        if action not in {"approve", "reject"}:
            raise SupplementError("Неизвестное действие")
        channel = await self._session.get(Channel, draft.channel_id)
        if (
            channel is None
            or not channel.is_active
            or channel.platform_id
            != draft.trace.get("configured_platform_id", draft.target_chat_id)
        ):
            raise SupplementError(
                "Канал выключен или изменился адрес; подготовьте новую карточку"
            )
        if action == "approve":
            validate_text(draft.text, draft.kind)
            if not draft.image_url:
                raise SupplementError("У этой версии нет обложки")
            self._check_freshness(draft)
        draft.status = "approved" if action == "approve" else "rejected"
        draft.decided_by = user_id
        draft.decided_at = datetime.now(UTC)
        await self._session.commit()
        logger.info(
            "Решение редактора сохранено",
            draft_id=draft_id,
            action=action,
            user_id=user_id,
        )
        return cast(str, draft.status)

    def _check_freshness(self, draft: SupplementDraft) -> None:
        if draft.kind == "news" and (
            not draft.sources
            or any(
                not _fresh(
                    TavilySearchResult(
                        title=str(s.get("title", "")),
                        url=str(s.get("url", "")),
                        content=str(s.get("content", "")),
                        published_date=s.get("published_date"),
                    ),
                    datetime.now(UTC),
                )
                for s in draft.sources
            )
        ):
            raise SupplementError(
                "Новость устарела или её дата не подтверждена; подготовьте новую"
            )

    async def publish(self, draft_id: int) -> None:
        """Отправляет одобренный снимок текста не более одного раза автоматически.

        Args:
            draft_id: Одобренный материал.

        Raises:
            SupplementError: Черновик не найден.
        """
        draft = await self.repo.draft(draft_id)
        if draft.status != "approved":
            await self._session.commit()
            return
        config = await self.repo.config(draft.channel_id)
        channel = await self._session.get(Channel, draft.channel_id)
        try:
            if draft.decided_by != config.recipient_id or draft.decided_at is None:
                raise SupplementError("Редактор изменён; требуется новое согласование")
            if (
                channel is None
                or not channel.is_active
                or channel.platform != "max"
                or channel.platform_id
                != draft.trace.get("configured_platform_id", draft.target_chat_id)
            ):
                raise SupplementError("Канал выключен или изменён после согласования")
            self._check_freshness(draft)
            validate_text(draft.text, draft.kind)
            image_bytes = await self._image_bytes(draft)
            if not re.fullmatch(r"-?\d+", draft.target_chat_id):
                raise SupplementError(
                    "Для согласования укажите числовой ID канала MAX в "
                    "настройках канала"
                )
        except SupplementError as exc:
            draft.status, draft.error = "publish_failed", str(exc)
            await self._session.commit()
            await self._update_status(draft)
            return
        draft.status = "publishing"
        await self._session.commit()
        try:
            result = await self._max.send(
                publication_text(draft),
                chat_id=draft.target_chat_id,
                image_bytes=image_bytes,
            )
        except DeliveryUncertain as exc:
            draft.status, draft.error = "publish_unknown", str(exc)
        except SupplementError as exc:
            draft.status, draft.error = "publish_failed", str(exc)
        else:
            draft.platform_mid, draft.platform_url = result["mid"], result["url"]
            draft.status, draft.error = "published", None
            post = ProcessedPost(
                channel_id=draft.channel_id,
                rewritten_text=publication_text(draft),
                article_title=draft.title,
                generated_image_url=draft.image_url,
                image_source=draft.image_source,
                content_mode="news",
                status="published",
                published_at=datetime.now(UTC),
                ai_model="supplement",
                research_sources=json.dumps(draft.sources, ensure_ascii=False),
                article_meta=json.dumps(
                    {"supplement_id": draft.id, "supplement_kind": draft.kind},
                    ensure_ascii=False,
                ),
                publish_text_hash=hashlib.sha256(
                    publication_text(draft).encode()
                ).hexdigest(),
            )
            self._session.add(post)
            await self._session.flush()
            await MediaAssetService(self._session).register_from_post(
                post,
                title=draft.title,
            )
            draft.processed_post_id = post.id
            self._session.add(
                PublishLog(
                    processed_post_id=post.id,
                    channel_id=draft.channel_id,
                    platform_post_id=draft.platform_mid,
                    status="success",
                )
            )
        await self._session.commit()
        await self._update_status(draft)

    async def _update_status(self, draft: SupplementDraft) -> None:
        if not draft.review_mid:
            return
        status_text = (
            "Опубликовано"
            if draft.status == "published"
            else "Не опубликовано: " + str(draft.error or draft.status)
        )
        try:
            await self._max.update_review(
                draft.review_mid,
                (
                    f"{status_text}\n{draft.platform_url or ''}\n\n"
                    f"{publication_text(draft)}"
                ),
            )
        except SupplementError:
            draft.trace = {
                **draft.trace,
                "notification_error": (
                    "Не удалось обновить карточку MAX; " "актуальный статус в GUI"
                ),
            }
            await self._session.commit()

    async def edit(self, draft_id: int, text: str) -> None:
        """Редактирует текст и отзывает предыдущие кнопки.

        Args:
            draft_id: Материал на проверке.
            text: Новый обычный текст.

        Raises:
            SupplementError: Материал уже публикуется или нарушает формат.
        """
        draft = await self.repo.draft(draft_id)
        if draft.status not in _EDITABLE:
            raise SupplementError("Этот материал сейчас нельзя редактировать")
        validate_text(text, draft.kind)
        draft.trace = {
            **draft.trace,
            "edits": [
                *draft.trace.get("edits", []),
                {
                    "revision": draft.revision,
                    "text": draft.text,
                    "at": datetime.now(UTC).isoformat(),
                },
            ],
        }
        draft.text = text.strip()
        if not draft.image_prompt:
            draft.image_prompt = (
                f"Научно-популярная иллюстрация к теме «{draft.title}»: "
                f"{draft.text}"
            )
        draft.revision += 1
        draft.review_mid = None
        draft.image_url = None
        draft.image_source = None
        draft.trace = {**draft.trace, "regenerate_image_only": True}
        draft.status, draft.error = "queued", None
        draft.progress_stage = "queued"
        draft.progress_percent = 5
        draft.progress_detail = "Задание ожидает запуска"
        draft.progress_updated_at = datetime.now(UTC)
        draft.decided_by, draft.decided_at = None, None
        await self._session.commit()

    async def retry(self, draft_id: int, *, confirmed_absent: bool = False) -> None:
        """Возобновляет ошибку только явным действием редактора в GUI.

        Args:
            draft_id: Материал с ошибкой.
            confirmed_absent: Редактор проверил отсутствие поста в канале.

        Raises:
            SupplementError: Повтор опасен или состояние не допускает повтор.
        """
        draft = await self.repo.draft(draft_id)
        if draft.status == "publish_unknown" and not confirmed_absent:
            raise SupplementError(
                "Сначала проверьте канал и подтвердите отсутствие поста"
            )
        if draft.status not in {
            "generation_failed",
            "delivery_failed",
            "delivery_unknown",
            "publish_failed",
            "publish_unknown",
        }:
            raise SupplementError("Для этого состояния повтор недоступен")
        draft.trace = {
            **draft.trace,
            "retries": [
                *draft.trace.get("retries", []),
                {
                    "at": datetime.now(UTC).isoformat(),
                    "status": draft.status,
                    "error": draft.error,
                    "confirmed_absent": confirmed_absent,
                },
            ],
        }
        draft.status = (
            "queued" if draft.status == "generation_failed" else "review_pending"
        )
        if draft.status == "queued":
            draft.progress_stage = "queued"
            draft.progress_percent = 5
            draft.progress_detail = "Задание ожидает запуска"
            draft.progress_updated_at = datetime.now(UTC)
        draft.revision += 1
        draft.review_mid, draft.error = None, None
        draft.decided_at, draft.decided_by = None, None
        await self._session.commit()

    async def create_pair_token(self, channel_id: int) -> str:
        """Выдаёт одноразовый токен привязки, сохраняя только хеш.

        Args:
            channel_id: Канал.

        Returns:
            Токен сроком на пятнадцать минут.

        Raises:
            SupplementError: Канал не найден.
        """
        config = await self.repo.config(channel_id)
        token = secrets.token_urlsafe(_TOKEN_BYTES)
        config.pair_hash = hashlib.sha256(token.encode()).hexdigest()
        config.pair_expires_at = datetime.now(UTC) + timedelta(minutes=PAIR_TTL_MINUTES)
        await self._session.commit()
        return token

    async def bind(self, token: str, user_id: int, name: str) -> None:
        """Привязывает автора заверенного bot_started и погашает токен.

        Args:
            token: Одноразовый параметр ссылки.
            user_id: Пользователь MAX.
            name: Отображаемое имя.

        Raises:
            SupplementError: Токен истёк или уже использован.
        """
        if user_id <= 0 or not token:
            raise SupplementError("Некорректное событие привязки")
        digest = hashlib.sha256(token.encode()).hexdigest()
        config = await self._session.scalar(
            select(SupplementConfig)
            .where(SupplementConfig.pair_hash == digest)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if (
            config is None
            or config.pair_expires_at is None
            or _utc(config.pair_expires_at) <= datetime.now(UTC)
        ):
            raise SupplementError(
                "Ссылка истекла или уже использована; создайте новую в GUI"
            )
        config.recipient_id, config.recipient_name = user_id, name[:255]
        config.pair_hash, config.pair_expires_at = None, None
        await self._session.commit()
        logger.info(
            "Редактор MAX подключён", channel_id=config.channel_id, user_id=user_id
        )

    async def recover_stale(self) -> None:
        """Отмечает прерванные операции, не повторяя сомнительную отправку.

        Raises:
            SupplementError: Не используется; ошибки БД передаются вызывающему коду.
        """
        cutoff = datetime.now(UTC) - timedelta(minutes=STALE_MINUTES)
        rows = await self._session.scalars(
            select(SupplementDraft)
            .where(
                SupplementDraft.status.in_(["generating", "delivering", "publishing"]),
                SupplementDraft.updated_at < cutoff,
            )
            .with_for_update(skip_locked=True)
        )
        mapping = {
            "generating": "generation_failed",
            "delivering": "delivery_unknown",
            "publishing": "publish_unknown",
        }
        for draft in rows:
            draft.status = mapping[draft.status]
            draft.error = "Операция прервана. Проверьте результат в MAX перед повтором."
        await self._session.commit()
