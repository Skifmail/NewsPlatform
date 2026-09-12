"""Безопасный транспорт личного согласования и точного текста публикации."""

import re
from typing import Any, Final
from urllib.parse import quote, urlsplit

import aiohttp

from app.core.config import get_settings
from app.domain.supplements import DeliveryUncertain, SupplementError
from app.utils.max_api import get_max_api_base, max_client_session

_TIMEOUT: Final = 25


class MaxReviewClient:
    """Обращается к существующему MAX-боту без автоматических повторов POST.

    Attributes:
        Отсутствуют: токен берётся из конфигурации и не возвращается клиенту.
    """

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Выполняет запрос, не раскрывая токены и тела ошибок MAX.

        Args:
            method: HTTP-метод.
            path: Фиксированный путь MAX API.
            params: Параметры запроса.
            body: Тело JSON.

        Returns:
            Ответ API.

        Raises:
            SupplementError: Нет токена или API явно отклонил запрос.
            DeliveryUncertain: Таймаут, ошибка сервера или невалидный ответ.
        """
        token = get_settings().max_bot_token
        if not token:
            raise SupplementError("MAX_BOT_TOKEN не настроен")
        try:
            async with max_client_session(
                timeout=aiohttp.ClientTimeout(total=_TIMEOUT)
            ) as http:
                async with http.request(
                    method,
                    f"{get_max_api_base()}{path}",
                    params=params,
                    json=body,
                    headers={"Authorization": token},
                ) as response:
                    if response.status >= 500:
                        raise DeliveryUncertain(
                            "MAX не подтвердил результат; проверьте сообщения вручную"
                        )
                    if response.status >= 400:
                        raise SupplementError(
                            f"MAX отклонил запрос: HTTP {response.status}"
                        )
                    data = await response.json()
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            if isinstance(exc, SupplementError):
                raise
            raise DeliveryUncertain(
                "Нет подтверждения MAX; автоматический повтор запрещён"
            ) from exc
        if not isinstance(data, dict):
            raise DeliveryUncertain("MAX вернул некорректный ответ")
        return data

    async def resolve_chat_id(self, address: str) -> str:
        """Разрешает адрес канала в неизменяемый числовой идентификатор.

        Args:
            address: Числовой ID, публичная ссылка или имя MAX.

        Returns:
            Числовой идентификатор для сохранения в карточке.

        Raises:
            SupplementError: Адрес или ответ MAX некорректен.
        """
        raw = address.strip()
        if re.fullmatch(r"-?\d+", raw):
            return raw
        if "://" in raw:
            parsed = urlsplit(raw)
            if parsed.hostname not in {"max.ru", "www.max.ru"}:
                raise SupplementError("Нужна ссылка канала MAX")
            raw = parsed.path.strip("/")
        raw = raw.removeprefix("@")
        if not raw or "/" in raw:
            raise SupplementError("Некорректный адрес канала MAX")
        result = await self.request("GET", f"/chats/{quote(raw, safe='')}")
        chat_id = result.get("chat_id")
        if type(chat_id) is not int:
            raise SupplementError("MAX не подтвердил числовой адрес канала")
        return str(chat_id)

    async def send(
        self,
        text: str,
        *,
        user_id: int | None = None,
        chat_id: str | None = None,
        buttons: list[list[dict[str, str]]] | None = None,
    ) -> dict[str, str]:
        """Отправляет ровно переданный обычный текст, без незаметного оформления.

        Args:
            text: Точный текст, включая источники.
            user_id: Личный получатель.
            chat_id: Канал назначения.
            buttons: Кнопки только личной карточки.

        Returns:
            Идентификатор и ссылка на сообщение.

        Raises:
            SupplementError: Адрес некорректен или API отклонил сообщение.
            DeliveryUncertain: Отправка не подтверждена.
        """
        if (user_id is None) == (chat_id is None):
            raise SupplementError("Нужен ровно один адресат")
        params = (
            {"user_id": str(user_id)}
            if user_id is not None
            else {"chat_id": str(chat_id)}
        )
        params["disable_link_preview"] = "true"
        body: dict[str, Any] = {"text": text}
        if buttons:
            body["attachments"] = [
                {"type": "inline_keyboard", "payload": {"buttons": buttons}}
            ]
        data = await self.request("POST", "/messages", params=params, body=body)
        message = data.get("message", {})
        mid = message.get("body", {}).get("mid") if isinstance(message, dict) else None
        if not mid:
            raise DeliveryUncertain(
                "MAX не вернул идентификатор отправленного сообщения"
            )
        return {"mid": str(mid), "url": str(message.get("url") or "")}

    async def update_review(self, mid: str, text: str) -> None:
        """Обновляет карточку и убирает обработанные кнопки.

        Args:
            mid: Сообщение согласования.
            text: Новый статус вместе с прежним текстом.

        Raises:
            SupplementError: MAX отклонил изменение.
        """
        await self.request(
            "PUT",
            "/messages",
            params={"message_id": mid},
            body={"text": text, "attachments": []},
        )
