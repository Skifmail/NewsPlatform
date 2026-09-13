"""Проверки адресации существующего MAX-бота без сетевых запросов."""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from app.domain.supplements import SupplementError
from app.infrastructure.publishers.max_review_client import MaxReviewClient


@pytest.mark.parametrize(
    "address", ["https://max.ru/paragraph", "@paragraph", "paragraph"]
)
async def test_resolve_when_public_link_should_return_numeric_id(
    mocker: MockerFixture, address: str
) -> None:
    """Публичный адрес разрешается до показа карточки редактору."""
    request = mocker.patch.object(
        MaxReviewClient, "request", new=AsyncMock(return_value={"chat_id": -10})
    )
    assert await MaxReviewClient().resolve_chat_id(address) == "-10"
    request.assert_awaited_once_with("GET", "/chats/paragraph")


async def test_resolve_when_numeric_should_not_request(mocker: MockerFixture) -> None:
    """Числовой адрес не требует обращения к API."""
    request = mocker.patch.object(MaxReviewClient, "request", new=AsyncMock())
    assert await MaxReviewClient().resolve_chat_id("-10") == "-10"
    request.assert_not_awaited()


async def test_resolve_when_invalid_response_should_fail(mocker: MockerFixture) -> None:
    """Неподтверждённый адрес не используется для отправки."""
    mocker.patch.object(MaxReviewClient, "request", new=AsyncMock(return_value={}))
    with pytest.raises(SupplementError):
        await MaxReviewClient().resolve_chat_id("paragraph")


async def test_send_when_image_provided_should_attach_image_before_keyboard(
    mocker: MockerFixture,
) -> None:
    """Карточка согласования содержит ту же картинку и кнопки решения."""
    client = MaxReviewClient()
    upload = mocker.patch.object(
        client, "_upload_image", new=AsyncMock(return_value="image-token")
    )
    request = mocker.patch.object(
        client,
        "request",
        new=AsyncMock(return_value={"message": {"body": {"mid": "mid"}}}),
    )
    buttons = [[{"type": "callback", "text": "Одобрить", "payload": "ok"}]]

    await client.send("Текст", user_id=7, buttons=buttons, image_bytes=b"jpeg")

    upload.assert_awaited_once_with(b"jpeg")
    body = request.await_args.kwargs["body"]
    assert body["attachments"] == [
        {"type": "image", "payload": {"token": "image-token"}},
        {"type": "inline_keyboard", "payload": {"buttons": buttons}},
    ]
