"""Отдельное защищённое пространство событий согласования MAX."""

import asyncio
import secrets
from typing import Any, Final

from kombu.exceptions import OperationalError
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.supplements import SupplementError
from app.infrastructure.publishers.max_review_client import MaxReviewClient
from app.repositories.setting_repository import SettingRepository
from app.services.supplement_service import SupplementService

SECRET_KEY: Final = "supplement_max_webhook_secret"
WEBHOOK_URL_KEY: Final = "supplement_max_webhook_url"
PAIR_PREFIX: Final = "extra_pair_"


async def webhook_secret(session: AsyncSession) -> str:
    """Читает секрет заверения MAX, не возвращаемый интерфейсу.

    Args:
        session: Сессия настроек.

    Returns:
        Секрет окружения либо настройки подключения.
    """
    return str(
        getattr(get_settings(), "max_webhook_secret", "")
        or await SettingRepository(session).get(SECRET_KEY, "")
    )


async def handle_supplement_update(
    session: AsyncSession, payload: dict[str, Any], secret: str | None
) -> bool:
    """Проверяет подлинность события перед привязкой или решением редактора.

    Args:
        session: Сессия БД.
        payload: Недоверенный JSON webhook.
        secret: Заголовок MAX.

    Returns:
        True для обработанного дополнительного события, False для старых кнопок.

    Raises:
        SupplementError: Секрет, пользователь или данные события некорректны.
    """
    callback = payload.get("callback")
    callback = callback if isinstance(callback, dict) else {}
    button = str(callback.get("payload") or "")
    start = str(payload.get("payload") or "")
    is_pair = payload.get("update_type") == "bot_started" and start.startswith(
        PAIR_PREFIX
    )
    is_decision = payload.get(
        "update_type"
    ) == "message_callback" and button.startswith("extra:")
    if not is_pair and not is_decision:
        return False
    expected = await webhook_secret(session)
    if not expected or not secret or not secrets.compare_digest(expected, secret):
        raise SupplementError("Недействительная подпись события MAX")
    service = SupplementService(session)
    if is_pair:
        user = payload.get("user")
        if not isinstance(user, dict) or type(user.get("user_id")) is not int:
            raise SupplementError("Нет пользователя в событии привязки")
        await service.bind(
            start.removeprefix(PAIR_PREFIX),
            user["user_id"],
            str(user.get("name") or user.get("first_name") or "Редактор"),
        )
        try:
            await MaxReviewClient().send(
                (
                    "Согласование подключено. Включите дополнительные "
                    "публикации в GUI. Без вашего одобрения материалы в канал "
                    "не отправляются."
                ),
                user_id=user["user_id"],
            )
        except SupplementError:
            logger.warning("Не удалось отправить подтверждение привязки MAX")
        return True
    user = callback.get("user")
    message = payload.get("message")
    if (
        not isinstance(user, dict)
        or type(user.get("user_id")) is not int
        or not isinstance(message, dict)
        or not isinstance(message.get("body"), dict)
    ):
        raise SupplementError("Некорректное событие согласования")
    parts = button.split(":")
    if len(parts) != 4 or not parts[1].isdigit() or not parts[2].isdigit():
        raise SupplementError("Некорректная кнопка")
    try:
        state = await service.decide(
            int(parts[1]),
            int(parts[2]),
            user["user_id"],
            str(message["body"].get("mid") or ""),
            parts[3],
        )
        text = (
            "Одобрено. Отправка в канал…"
            if state == "approved"
            else "Отклонено. В канал не отправлено."
        )
    except SupplementError as exc:
        await session.rollback()
        # Не меняем сообщение для чужого пользователя и не удаляем рабочие кнопки.
        logger.warning("Решение MAX отклонено", reason=str(exc))
        return True
    callback_id = str(callback.get("callback_id") or "")
    if callback_id:
        try:
            await MaxReviewClient().request(
                "POST",
                "/answers",
                params={"callback_id": callback_id},
                body={
                    "message": {
                        "text": text + "\n\n" + str(message["body"].get("text") or ""),
                        "attachments": [],
                    }
                },
            )
        except SupplementError:
            logger.warning("Не удалось обновить ответ MAX; решение сохранено")
    if state == "approved":
        from app.tasks.supplement_tasks import publish_supplement

        try:
            await asyncio.to_thread(
                publish_supplement.apply_async, args=[int(parts[1])], retry=False
            )
        except (OperationalError, OSError):
            logger.warning(
                "Брокер недоступен; сохранённое одобрение подхватит планировщик"
            )
    return True
