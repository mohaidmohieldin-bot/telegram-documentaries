"""The gateway replies to every new message with the same fixed text."""

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Message, Update
from telegram.ext import Application

from telegram_documentaries.gateway import REPLY_TEXT, build_application, reply

FAKE_TOKEN = "123456789:AAH-fake-token-for-tests"


def fake_update(chat_id: int = 42, has_message: bool = True) -> MagicMock:
    """A minimal stand-in for a Telegram update; reply_text is captured, not sent."""
    update = MagicMock(spec=Update)
    update.update_id = 1
    update.effective_chat = MagicMock(id=chat_id) if has_message else None
    if has_message:
        update.effective_message = MagicMock()
        update.effective_message.reply_text = AsyncMock()
    else:
        update.effective_message = None
    return update


def real_message(text: str | None = "hello") -> Message:
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=42, type=Chat.PRIVATE),
        text=text,
    )


def test_reply_text_is_the_hardcoded_greeting() -> None:
    assert REPLY_TEXT == "hey mate!"


async def test_replies_with_hardcoded_text() -> None:
    update = fake_update()
    await reply(update, MagicMock())
    update.effective_message.reply_text.assert_awaited_once_with(REPLY_TEXT)


async def test_every_message_gets_the_same_reply() -> None:
    updates = [fake_update(), fake_update(), fake_update()]
    for update in updates:
        await reply(update, MagicMock())
    for update in updates:
        update.effective_message.reply_text.assert_awaited_once_with(REPLY_TEXT)


async def test_replies_go_to_the_chat_that_sent_them() -> None:
    first, second = fake_update(chat_id=1), fake_update(chat_id=2)
    await reply(first, MagicMock())
    first.effective_message.reply_text.assert_awaited_once()
    second.effective_message.reply_text.assert_not_awaited()


async def test_update_without_a_message_is_ignored() -> None:
    update = fake_update(has_message=False)
    await reply(update, MagicMock())  # must not raise


async def test_logs_each_received_update_with_chat_id(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="telegram_documentaries")
    await reply(fake_update(chat_id=777), MagicMock())
    assert "event=update_received" in caplog.text
    assert "chat_id=777" in caplog.text


def application_handlers(app: Application) -> list:  # type: ignore[type-arg]
    return [h for group in app.handlers.values() for h in group]


@pytest.mark.parametrize("text", ["hi", "/start", "🦁 emoji", None])
def test_application_handles_any_new_message(text: str | None) -> None:
    app = build_application(FAKE_TOKEN)
    update = Update(update_id=1, message=real_message(text))
    assert any(h.check_update(update) for h in application_handlers(app))


def test_application_ignores_edited_messages() -> None:
    app = build_application(FAKE_TOKEN)
    update = Update(update_id=2, edited_message=real_message("edited"))
    assert not any(h.check_update(update) for h in application_handlers(app))


def test_application_registers_an_error_handler() -> None:
    app = build_application(FAKE_TOKEN)
    assert app.error_handlers
