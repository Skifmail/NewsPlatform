"""Проверки сохранённого согласования с изолированной БД и подменой MAX."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.supplements import SupplementError
from app.infrastructure.database import Base
from app.infrastructure.models.channel import Channel
from app.infrastructure.models.supplement import SupplementConfig, SupplementDraft
from app.services.supplement_service import SupplementService


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    """Создаёт отдельную БД, не использующую рабочие данные."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        db.add(
            Channel(
                id=1,
                name="ПАРАГРАФ",
                platform="max",
                platform_id="-10",
                topic="science",
                content_mode="article",
            )
        )
        db.add(SupplementConfig(channel_id=1, enabled=True, recipient_id=7))
        await db.commit()
        yield db
    await engine.dispose()


@pytest.fixture
def transport(mocker: MockerFixture) -> AsyncMock:
    """Подменяет отправку, исключая любые реальные публикации."""
    client = AsyncMock()
    client.send.return_value = {"mid": "sent", "url": "https://max.ru/c/10/sent"}
    mocker.patch("app.services.supplement_service.MaxReviewClient", return_value=client)
    mocker.patch.object(
        SupplementService,
        "_image_bytes",
        new=AsyncMock(return_value=b"same-image"),
    )
    return client


async def _draft(session: AsyncSession, state: str = "awaiting") -> SupplementDraft:
    draft = SupplementDraft(
        channel_id=1,
        slot_key="manual",
        requested_kind="fact",
        kind="fact",
        text="Металл проводит тепло.",
        status=state,
        decided_by=7 if state == "approved" else None,
        decided_at=datetime.now(UTC) if state == "approved" else None,
        review_mid="mid",
        revision=1,
        target_chat_id="-10",
        sources=[{"url": "https://nasa.gov/a"}],
        trace={
            "rules": "Наука простыми словами",
            "fact_rules": "Один короткий факт",
            "news_rules": "Два коротких предложения",
            "configured_platform_id": "-10",
            "channel_name": "ПАРАГРАФ",
        },
        image_url="local://covers/fact.png",
        image_source="generated",
        image_prompt="Металл и дерево на нейтральном фоне",
    )
    session.add(draft)
    await session.commit()
    return draft


async def test_decide_when_approved_should_queue_without_network(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Решение сохраняется до фоновой отправки и не теряется с брокером."""
    draft = await _draft(session)
    await SupplementService(session).decide(draft.id, 1, 7, "mid", "approve")
    assert draft.status == "approved"
    transport.send.assert_not_awaited()


async def test_decide_when_rejected_should_never_publish(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Отказ исключает отправку в канал."""
    draft = await _draft(session)
    service = SupplementService(session)
    await service.decide(draft.id, 1, 7, "mid", "reject")
    await service.publish(draft.id)
    assert draft.status == "rejected"
    transport.send.assert_not_awaited()


async def test_publish_when_approved_twice_should_send_once(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Повторная доставка задачи не создаёт второй пост."""
    draft = await _draft(session, "approved")
    service = SupplementService(session)
    await service.publish(draft.id)
    await service.publish(draft.id)
    assert draft.status == "published"
    assert draft.processed_post_id is not None
    assert transport.send.await_count == 1
    assert transport.send.await_args.kwargs["image_bytes"] == b"same-image"


async def test_publish_when_timeout_should_block_automatic_retry(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Неопределённый ответ сервера не приводит к слепому повтору."""
    from app.domain.supplements import DeliveryUncertain

    transport.send.side_effect = DeliveryUncertain("Нет подтверждения")
    draft = await _draft(session, "approved")
    service = SupplementService(session)
    await service.publish(draft.id)
    await service.publish(draft.id)
    assert draft.status == "publish_unknown"
    assert transport.send.await_count == 1


async def test_edit_when_waiting_should_invalidate_old_buttons(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """После редактирования нужно новое одобрение точного текста."""
    draft = await _draft(session)
    service = SupplementService(session)
    await service.edit(draft.id, "Дерево проводит тепло хуже металла.")
    assert draft.revision == 2
    assert draft.status == "queued"
    assert draft.image_url is None
    assert draft.trace["regenerate_image_only"] is True
    with pytest.raises(SupplementError):
        await service.decide(draft.id, 1, 7, "mid", "approve")
    transport.send.assert_not_awaited()


async def test_pair_when_token_used_should_reject_replay(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Привязочный токен одноразовый и не позволяет перехватить аккаунт."""
    service = SupplementService(session)
    token = await service.create_pair_token(1)
    await service.bind(token, 42, "Редактор")
    with pytest.raises(SupplementError):
        await service.bind(token, 99, "Чужой")
    config = await session.get(SupplementConfig, 1)
    assert config is not None and config.recipient_id == 42


async def test_pair_when_expired_should_reject(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Истёкшая ссылка не привязывает пользователя."""
    service = SupplementService(session)
    token = await service.create_pair_token(1)
    config = await session.get(SupplementConfig, 1)
    assert config is not None
    config.pair_expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await session.commit()
    with pytest.raises(SupplementError):
        await service.bind(token, 42, "Редактор")


async def test_decide_when_wrong_user_should_preserve_draft(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Знания идентификатора карточки недостаточно для публикации."""
    draft = await _draft(session)
    with pytest.raises(SupplementError):
        await SupplementService(session).decide(draft.id, 1, 99, "mid", "approve")
    assert draft.status == "awaiting"
    transport.send.assert_not_awaited()


async def test_reserve_when_same_slot_repeated_should_create_one_draft(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Повторный тик не резервирует московский слот дважды."""
    service = SupplementService(session)
    moment = datetime(2026, 9, 14, 15, tzinfo=UTC)
    first = await service.reserve(1, now=moment)
    second = await service.reserve(1, now=moment)
    assert first is not None and second is None


async def test_reserve_when_disabled_should_not_generate(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Выключенная рубрика не влияет на основное расписание."""
    config = await session.get(SupplementConfig, 1)
    assert config is not None
    config.enabled = False
    await session.commit()
    assert (
        await SupplementService(session).reserve(
            1, now=datetime(2026, 9, 14, 15, tzinfo=UTC)
        )
        is None
    )


async def test_deliver_when_waiting_should_send_only_to_editor(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Черновик не отправляется в канал при подготовке карточки."""
    draft = await _draft(session, "review_pending")
    await SupplementService(session).deliver(draft.id)
    assert draft.status == "awaiting"
    assert transport.send.call_args.kwargs["user_id"] == 7
    assert "chat_id" not in transport.send.call_args.kwargs
    assert transport.send.call_args.kwargs["image_bytes"] == b"same-image"
    assert "Одобрить" in str(transport.send.call_args.kwargs["buttons"])


async def test_decide_when_news_stale_should_not_approve(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Старая карточка новости не публикует устаревший материал."""
    draft = await _draft(session)
    draft.kind = "news"
    draft.text = "Учёные проверили гипотезу. Результат требует повторения."
    draft.sources = [{"url": "https://nasa.gov/a", "published_date": "2020-01-01"}]
    await session.commit()
    with pytest.raises(SupplementError, match="устарела"):
        await SupplementService(session).decide(draft.id, 1, 7, "mid", "approve")
    assert draft.status == "awaiting"


async def test_retry_when_uncertain_should_require_manual_confirmation(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Нельзя повторить потенциально успешную публикацию автоматически."""
    draft = await _draft(session, "publish_unknown")
    service = SupplementService(session)
    with pytest.raises(SupplementError):
        await service.retry(draft.id)
    await service.retry(draft.id, confirmed_absent=True)
    assert draft.status == "review_pending"
    assert draft.revision == 2
    transport.send.assert_not_awaited()


async def test_publish_when_channel_changed_should_not_send(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Одобрение старого канала не действует для нового адресата."""
    draft = await _draft(session, "approved")
    channel = await session.get(Channel, 1)
    assert channel is not None
    channel.platform_id = "-11"
    await session.commit()
    await SupplementService(session).publish(draft.id)
    assert draft.status == "publish_failed"
    transport.send.assert_not_awaited()


async def test_gui_when_config_requested_should_hide_pair_hash(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Служебные секреты отсутствуют в ответе GUI."""
    from app.api.routers.supplements import get_config

    await SupplementService(session).create_pair_token(1)
    response = await get_config(1, session, "admin")
    assert "pair_hash" not in response["config"]
    assert len(response["config"]["upcoming"]) >= 6


async def test_gui_when_approval_requested_should_reject_schema() -> None:
    """GUI не имеет обходного действия approve/publish."""
    from pydantic import ValidationError

    from app.api.routers.supplements import ActionInput

    with pytest.raises(ValidationError):
        ActionInput.model_validate({"action": "approve"})


async def test_recovery_when_publish_interrupted_should_mark_unknown(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Падение воркера во время отправки требует ручной проверки."""
    draft = await _draft(session, "publishing")
    draft.updated_at = datetime.now(UTC) - timedelta(hours=1)
    await session.commit()
    await SupplementService(session).recover_stale()
    await session.refresh(draft)
    assert draft.status == "publish_unknown"
    transport.send.assert_not_awaited()


async def test_publish_when_editor_changed_should_require_new_approval(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Смена редактора отменяет право отправки по прежнему решению."""
    draft = await _draft(session)
    service = SupplementService(session)
    await service.decide(draft.id, 1, 7, "mid", "approve")
    config = await session.get(SupplementConfig, 1)
    assert config is not None
    config.recipient_id = 8
    await session.commit()
    await service.publish(draft.id)
    assert draft.status == "publish_failed"
    transport.send.assert_not_awaited()


async def test_deliver_when_public_channel_should_pin_resolved_target(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Редактор одобряет конкретный канал, разрешённый до доставки карточки."""
    channel = await session.get(Channel, 1)
    assert channel is not None
    channel.platform_id = "https://max.ru/paragraph"
    draft = await _draft(session, "review_pending")
    draft.target_chat_id = channel.platform_id
    draft.trace = {"configured_platform_id": channel.platform_id}
    transport.resolve_chat_id.return_value = "-10"
    await session.commit()
    service = SupplementService(session)
    await service.deliver(draft.id)
    assert draft.target_chat_id == "-10"
    await service.decide(draft.id, 1, 7, "sent", "approve")
    await service.publish(draft.id)
    assert draft.status == "published"
    assert transport.send.call_args.kwargs["chat_id"] == "-10"


async def test_generate_when_text_ready_should_create_cover_before_review(
    session: AsyncSession, transport: AsyncMock, mocker: MockerFixture
) -> None:
    """Новый материал не попадает на согласование без сгенерированной обложки."""
    draft = await _draft(session, "queued")
    generator = mocker.patch("app.services.supplement_service.SupplementGenerator")
    generator.return_value.generate = AsyncMock(
        return_value={
            "kind": "fact",
            "title": "Как утконос ищет добычу",
            "text": "Утконос находит добычу, улавливая клювом электрические сигналы.",
            "sources": [{"url": "https://example.org/platypus"}],
            "image_prompt": "Утконос под водой ищет небольшую добычу",
            "trace": {"selection_reason": "Понятный факт"},
        }
    )
    images = AsyncMock()
    images.resolve_article_image.return_value = (
        "local://covers/platypus.png",
        "generated",
    )

    await SupplementService(session, image_service=images).generate(draft.id)

    assert draft.status == "review_pending"
    assert draft.image_url == "local://covers/platypus.png"
    assert draft.image_source == "generated"
    images.resolve_article_image.assert_awaited_once()


async def test_generate_when_cover_fails_should_not_deliver_text(
    session: AsyncSession, transport: AsyncMock, mocker: MockerFixture
) -> None:
    """Сбой обязательной картинки блокирует карточку и публикацию текста."""
    draft = await _draft(session, "queued")
    generator = mocker.patch("app.services.supplement_service.SupplementGenerator")
    generator.return_value.generate = AsyncMock(
        return_value={
            "kind": "fact",
            "title": "Кварц",
            "text": "Кварц вырабатывает напряжение, когда его сжимают.",
            "sources": [{"url": "https://example.org/quartz"}],
            "image_prompt": "Кристалл кварца под давлением",
            "trace": {},
        }
    )
    images = AsyncMock()
    images.resolve_article_image.return_value = (None, "none")
    service = SupplementService(session, image_service=images)

    await service.generate(draft.id)
    await service.deliver(draft.id)

    assert draft.status == "generation_failed"
    assert "облож" in str(draft.error).lower()
    transport.send.assert_not_awaited()


async def test_generate_when_pipeline_advances_should_persist_named_progress(
    session: AsyncSession, transport: AsyncMock, mocker: MockerFixture
) -> None:
    """Каждый длительный этап должен сохраняться для наблюдения из GUI."""
    draft = await _draft(session, "queued")
    observed: list[tuple[str, int, str]] = []

    async def generate_result(*args: object, **kwargs: object) -> dict[str, object]:
        progress = kwargs["progress"]
        await progress("searching", 30, "Ищем надёжные источники")  # type: ignore[operator]
        observed.append(
            (
                draft.progress_stage,
                draft.progress_percent,
                draft.progress_detail,
            )
        )
        await progress("writing", 50, "Пишем понятный текст")  # type: ignore[operator]
        observed.append(
            (
                draft.progress_stage,
                draft.progress_percent,
                draft.progress_detail,
            )
        )
        return {
            "kind": "fact",
            "title": "Как утконос ищет добычу",
            "text": "Утконос находит добычу, улавливая клювом электрические сигналы.",
            "sources": [{"url": "https://example.org/platypus"}],
            "image_prompt": "Утконос под водой ищет небольшую добычу",
            "trace": {"selection_reason": "Понятный факт"},
        }

    generator = mocker.patch("app.services.supplement_service.SupplementGenerator")
    generator.return_value.generate = AsyncMock(side_effect=generate_result)
    images = AsyncMock()
    images.resolve_article_image.return_value = (
        "local://covers/platypus.png",
        "generated",
    )

    await SupplementService(session, image_service=images).generate(draft.id)

    assert observed == [
        ("searching", 30, "Ищем надёжные источники"),
        ("writing", 50, "Пишем понятный текст"),
    ]
    assert draft.progress_stage == "ready_for_delivery"
    assert draft.progress_percent == 88
    assert draft.progress_updated_at is not None


async def test_retry_when_generation_failed_should_reset_progress(
    session: AsyncSession, transport: AsyncMock
) -> None:
    """Повтор подготовки должен начинать индикатор с очереди."""
    draft = await _draft(session, "generation_failed")
    draft.progress_stage = "failed"
    draft.progress_percent = 50
    draft.progress_detail = "Подготовка остановлена"
    await session.commit()

    await SupplementService(session).retry(draft.id)

    assert draft.status == "queued"
    assert draft.progress_stage == "queued"
    assert draft.progress_percent == 5
    assert draft.progress_detail == "Задание ожидает запуска"
