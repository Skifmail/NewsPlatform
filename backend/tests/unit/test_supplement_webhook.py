"""Граница доверия событий MAX для модерации."""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from app.domain.supplements import SupplementError
from app.services.supplement_webhook import handle_supplement_update


@pytest.mark.parametrize("secret", [None, "wrong", ""])
async def test_webhook_when_missing_or_wrong_secret_should_deny(
    mocker: MockerFixture, secret: str | None
) -> None:
    """Без заверенного события никакие решения не принимаются."""
    mocker.patch(
        "app.services.supplement_webhook.webhook_secret",
        new=AsyncMock(return_value="expected"),
    )
    service = mocker.patch("app.services.supplement_webhook.SupplementService")
    with pytest.raises(SupplementError):
        await handle_supplement_update(
            AsyncMock(),
            {
                "update_type": "message_callback",
                "callback": {"payload": "extra:1:1:approve"},
            },
            secret,
        )
    service.assert_not_called()


async def test_webhook_when_reader_button_should_leave_legacy_handler(
    mocker: MockerFixture,
) -> None:
    """Опросы читателей не превращаются в согласование."""
    assert not await handle_supplement_update(
        AsyncMock(),
        {"update_type": "message_callback", "callback": {"payload": "paragraph:1:0"}},
        None,
    )


async def test_webhook_when_valid_callback_should_use_callback_author(
    mocker: MockerFixture,
) -> None:
    """Проверяет автора callback, а не отправителя сообщения-бота."""
    mocker.patch(
        "app.services.supplement_webhook.webhook_secret",
        new=AsyncMock(return_value="expected"),
    )
    dispatch = mocker.patch("app.tasks.supplement_tasks.publish_supplement.apply_async")
    service = AsyncMock()
    service.decide.return_value = "approved"
    mocker.patch(
        "app.services.supplement_webhook.SupplementService", return_value=service
    )
    mocker.patch(
        "app.services.supplement_webhook.MaxReviewClient", return_value=AsyncMock()
    )
    assert await handle_supplement_update(
        AsyncMock(),
        {
            "update_type": "message_callback",
            "callback": {
                "payload": "extra:1:2:approve",
                "callback_id": "cb",
                "user": {"user_id": 7},
            },
            "message": {"sender": {"user_id": 99}, "body": {"mid": "mid"}},
        },
        "expected",
    )
    service.decide.assert_awaited_once_with(1, 2, 7, "mid", "approve")
    dispatch.assert_called_once_with(args=[1], retry=False)


def test_settings_when_review_secret_should_be_internal() -> None:
    """Секрет согласования нельзя прочитать или заменить через общие настройки."""
    from app.domain.platform_settings import is_internal_setting_key

    assert is_internal_setting_key("supplement_max_webhook_secret")
    assert is_internal_setting_key("supplement_max_webhook_url")
