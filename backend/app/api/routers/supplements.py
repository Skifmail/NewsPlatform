"""GUI API дополнительных материалов и безопасного подключения MAX."""

import ipaddress
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal
from urllib.parse import quote, urlsplit

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select

from app.api.deps import AuthDep, DbSession
from app.core.config import get_settings
from app.domain.supplements import MOSCOW, SupplementError, due_kind
from app.infrastructure.models.supplement import SupplementConfig, SupplementDraft
from app.infrastructure.publishers.max_review_client import MaxReviewClient
from app.repositories.setting_repository import SettingRepository
from app.services.supplement_service import SupplementService, publication_text
from app.services.supplement_webhook import (
    PAIR_PREFIX,
    SECRET_KEY,
    WEBHOOK_URL_KEY,
    webhook_secret,
)

router = APIRouter(prefix="/supplements", tags=["supplements"])
_LIST_LIMIT: Final = 100
_CALENDAR_DAYS: Final = 14


class ConfigInput(BaseModel):
    """Редактируемые настройки без полей привязки и служебных секретов.

    Attributes:
        enabled: Подготавливать по расписанию.
        clock: Московское время отправки на согласование.
        rules: Редакционные правила.
    """

    model_config = ConfigDict(extra="forbid")
    enabled: bool
    clock: str = "18:00"
    fact_days: list[int] = Field(default_factory=lambda: [0, 4])
    news_day: int = 2
    rules: str = Field(min_length=1, max_length=6000)
    fact_rules: str = Field(min_length=1, max_length=3000)
    news_rules: str = Field(min_length=1, max_length=3000)

    @model_validator(mode="after")
    def validate_schedule(self) -> "ConfigInput":
        """Проверяет время и отсутствие пересечения дней.

        Returns:
            Проверенная настройка.

        Raises:
            SupplementError: Расписание некорректно.
        """
        due_kind(datetime.now(UTC), self.clock, self.fact_days, self.news_day)
        return self


class SetupInput(BaseModel):
    """Адрес платформы для подписки существующего бота.

    Attributes:
        url: Публичный HTTPS-адрес webhook этой платформы.
    """

    url: str = Field(max_length=500)


class GenerateInput(BaseModel):
    """Ручная подготовка без публикации.

    Attributes:
        kind: Запрашиваемый формат.
    """

    kind: Literal["fact", "news"]


class ActionInput(BaseModel):
    """Действие GUI, не позволяющее обойти согласование в MAX.

    Attributes:
        action: Разрешённое действие, без approve/publish.
        text: Исправленный текст.
        confirmed_absent: Подтверждение ручной проверки канала.
    """

    action: Literal["edit", "retry", "skip", "regenerate"]
    text: str = Field(default="", max_length=1000)
    confirmed_absent: bool = False


def _config_response(config: SupplementConfig) -> dict[str, Any]:
    response = {
        key: getattr(config, key)
        for key in (
            "channel_id",
            "enabled",
            "clock",
            "fact_days",
            "news_day",
            "rules",
            "fact_rules",
            "news_rules",
            "recipient_id",
            "recipient_name",
        )
    }
    now = datetime.now(MOSCOW)
    schedule = []
    for offset in range(_CALENDAR_DAYS + 1):
        local = (now + timedelta(days=offset)).replace(
            hour=int(config.clock[:2]),
            minute=int(config.clock[3:]),
            second=0,
            microsecond=0,
        )
        if local <= now:
            continue
        kind = due_kind(local, config.clock, config.fact_days, config.news_day)
        if kind:
            schedule.append({"at": local.isoformat(), "kind": kind})
    response["upcoming"] = schedule
    return response


def _draft_response(draft: SupplementDraft) -> dict[str, Any]:
    keys = (
        "id",
        "channel_id",
        "requested_kind",
        "kind",
        "title",
        "text",
        "sources",
        "trace",
        "status",
        "revision",
        "target_chat_id",
        "error",
        "decided_by",
        "decided_at",
        "platform_url",
        "platform_mid",
        "created_at",
        "updated_at",
    )
    return {
        **{key: getattr(draft, key) for key in keys},
        "publication_text": publication_text(draft) if draft.text else "",
    }


@router.get("/connection")
async def connection(session: DbSession, _: AuthDep) -> dict[str, Any]:
    """Показывает сохранённую настройку подключения, не раскрывая секрет.

    Args:
        session: Сессия БД.
        _: Авторизованный администратор.

    Returns:
        Признаки настройки и адрес обработчика.
    """
    return {
        "bot_configured": bool(get_settings().max_bot_token),
        "webhook_url": await SettingRepository(session).get(WEBHOOK_URL_KEY, ""),
        "secret_configured": bool(await webhook_secret(session)),
    }


@router.post("/connection")
async def setup_connection(
    body: SetupInput, session: DbSession, _: AuthDep
) -> dict[str, str]:
    """Регистрирует защищённый обработчик, сохраняя существующие типы событий.

    Args:
        body: Публичный адрес обработчика.
        session: Сессия БД.
        _: Авторизованный администратор.

    Returns:
        Подтверждение настройки.

    Raises:
        HTTPException: Адрес неверен или MAX не подтвердил подписку.
    """
    parsed = urlsplit(body.url)
    hostname = parsed.hostname or ""
    try:
        private_host = not ipaddress.ip_address(hostname).is_global
    except ValueError:
        private_host = (
            hostname == "localhost"
            or hostname.endswith((".local", ".internal"))
            or "." not in hostname
        )
    if (
        parsed.scheme != "https"
        or private_host
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path != "/api/webhooks/max"
    ):
        raise HTTPException(
            422, "Укажите публичный HTTPS-адрес платформы с путём /api/webhooks/max"
        )
    settings = SettingRepository(session)
    secret = await webhook_secret(session) or secrets.token_urlsafe(32)
    await settings.set(SECRET_KEY, secret)
    await session.commit()
    client = MaxReviewClient()
    try:
        existing = await client.request("GET", "/subscriptions")
        event_types: set[str] = {"bot_started", "message_callback"}
        all_events = False
        for subscription in existing.get("subscriptions", []):
            if subscription.get("url") == body.url:
                previous_types = subscription.get("update_types")
                if not previous_types:
                    all_events = True
                else:
                    event_types.update(str(item) for item in previous_types)
        request: dict[str, Any] = {"url": body.url, "secret": secret}
        if not all_events:
            request["update_types"] = sorted(event_types)
        result = await client.request("POST", "/subscriptions", body=request)
        if result.get("success") is not True:
            raise SupplementError("MAX не подтвердил подписку")
    except SupplementError as exc:
        raise HTTPException(502, str(exc)) from exc
    await settings.set(WEBHOOK_URL_KEY, body.url)
    await session.commit()
    return {"message": "Обработчик MAX подключён. Теперь привяжите редактора."}


@router.get("/{channel_id}")
async def get_config(channel_id: int, session: DbSession, _: AuthDep) -> dict[str, Any]:
    """Возвращает настройки, календарь и историю без секретов.

    Args:
        channel_id: Канал MAX.
        session: Сессия БД.
        _: Авторизованный администратор.

    Returns:
        Настройки и до ста последних материалов.

    Raises:
        HTTPException: Канал не найден.
    """
    try:
        config = await SupplementService(session).repo.config(channel_id)
    except SupplementError as exc:
        raise HTTPException(404, str(exc)) from exc
    rows = await session.scalars(
        select(SupplementDraft)
        .where(SupplementDraft.channel_id == channel_id)
        .order_by(SupplementDraft.id.desc())
        .limit(_LIST_LIMIT)
    )
    result = {
        "config": _config_response(config),
        "drafts": [_draft_response(draft) for draft in rows],
    }
    await session.commit()
    return result


@router.put("/{channel_id}")
async def save_config(
    channel_id: int, body: ConfigInput, session: DbSession, _: AuthDep
) -> dict[str, Any]:
    """Сохраняет правила; включение требует привязанного редактора.

    Args:
        channel_id: Канал.
        body: Настройки.
        session: Сессия БД.
        _: Администратор.

    Returns:
        Обновлённые настройки.

    Raises:
        HTTPException: Канал или согласование не настроены.
    """
    try:
        config = await SupplementService(session).repo.config(channel_id)
        if body.enabled and (
            config.recipient_id is None
            or not await webhook_secret(session)
            or not await SettingRepository(session).get(WEBHOOK_URL_KEY, "")
        ):
            raise SupplementError("Сначала подключите обработчик MAX и редактора")
        for key, value in body.model_dump().items():
            setattr(config, key, value)
        await session.commit()
        return _config_response(config)
    except SupplementError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{channel_id}/pair")
async def pair(channel_id: int, session: DbSession, _: AuthDep) -> dict[str, str]:
    """Создаёт ссылку для привязки личного диалога с существующим ботом.

    Args:
        channel_id: Канал.
        session: Сессия БД.
        _: Администратор.

    Returns:
        Одноразовая ссылка без токена бота.

    Raises:
        HTTPException: Обработчик не подключён или бот недоступен.
    """
    try:
        if not await webhook_secret(session) or not await SettingRepository(
            session
        ).get(WEBHOOK_URL_KEY, ""):
            raise SupplementError("Сначала подключите обработчик MAX")
        info = await MaxReviewClient().request("GET", "/me")
        username = str(info.get("username") or "").strip().lstrip("@")
        if not username or "/" in username:
            raise SupplementError("MAX не вернул публичное имя бота")
        token = await SupplementService(session).create_pair_token(channel_id)
        return {
            "url": (
                f"https://max.ru/{quote(username, safe='')}"
                f"?start={PAIR_PREFIX}{token}"
            )
        }
    except SupplementError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/{channel_id}/generate")
async def generate(
    channel_id: int, body: GenerateInput, session: DbSession, _: AuthDep
) -> dict[str, int | None]:
    """Создаёт ручное задание только для личного согласования.

    Args:
        channel_id: Канал.
        body: Формат.
        session: Сессия БД.
        _: Администратор.

    Returns:
        Идентификатор сохранённого задания.

    Raises:
        HTTPException: Канал не готов.
    """
    try:
        return {
            "id": await SupplementService(session).reserve(
                channel_id, manual_kind=body.kind
            )
        }
    except SupplementError as exc:
        raise HTTPException(422, str(exc)) from exc


@router.post("/drafts/{draft_id}/action")
async def draft_action(
    draft_id: int, body: ActionInput, session: DbSession, _: AuthDep
) -> dict[str, str]:
    """Изменяет черновик без права опубликовать его из GUI.

    Args:
        draft_id: Материал.
        body: Исправление, повтор, пропуск или новая генерация.
        session: Сессия БД.
        _: Администратор.

    Returns:
        Подтверждение.

    Raises:
        HTTPException: Состояние не допускает действия.
    """
    service = SupplementService(session)
    try:
        if body.action == "edit":
            await service.edit(draft_id, body.text)
        elif body.action == "retry":
            await service.retry(draft_id, confirmed_absent=body.confirmed_absent)
        else:
            draft = await service.repo.draft(draft_id)
            if draft.status not in {
                "awaiting",
                "review_pending",
                "rejected",
                "generation_failed",
                "delivery_failed",
                "delivery_unknown",
                "publish_failed",
            }:
                raise SupplementError(
                    "Сейчас нельзя отменить или перегенерировать материал"
                )
            draft.status = "rejected"
            draft.revision += 1
            draft.trace = {
                **draft.trace,
                "gui_action": body.action,
                "gui_actor": _,
                "gui_action_at": datetime.now(UTC).isoformat(),
            }
            await session.commit()
            if body.action == "regenerate":
                await service.reserve(
                    draft.channel_id, manual_kind=draft.requested_kind
                )
        return {"message": "Изменения сохранены; публикация требует одобрения в MAX"}
    except SupplementError as exc:
        raise HTTPException(409, str(exc)) from exc
