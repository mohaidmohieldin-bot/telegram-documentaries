"""Phase 7: resets from any phase, command menu, crash replies, timeouts, and a sweep of
every phase x every kind of input (the "wrong payload at the wrong stage" category)."""

import logging
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import BotCommand, MessageEntity, Update
from telegram.error import NetworkError

from telegram_documentaries import gateway
from telegram_documentaries.gateway import Deps, build_application
from telegram_documentaries.session import Phase, Session
from tests.test_gateway import (
    FAKE_TOKEN,
    PHOTO,
    FakeBouncer,
    FakeInterviewer,
    ask,
    completed,
    fake_message,
    fake_update,
    interviewing,
    make_context,
    make_deps,
    matching_callbacks,
    portrait_delivered,
    real_message,
    script_ready,
    telegram_file,
)

# --- Putting a chat into each phase ------------------------------------------------------


def done(deps: Deps) -> Deps:
    script_ready(deps).sessions.finish(42)
    return deps


SETUPS: dict[Phase, Callable[[Deps], Deps]] = {
    Phase.AWAITING_PHOTO: lambda deps: deps,
    Phase.INTERVIEWING: lambda deps: interviewing(deps, "Q1?"),
    Phase.INTERVIEW_COMPLETE: completed,
    Phase.PORTRAIT_DELIVERED: portrait_delivered,
    Phase.SCRIPT_READY: script_ready,
    Phase.DONE: done,
}


def deps_in(phase: Phase) -> Deps:
    deps = make_deps(FakeBouncer(), FakeInterviewer("Q1?", ask("Q2?")))
    SETUPS[phase](deps)
    assert deps.sessions.get(42).phase is phase
    return deps


def replies_of(message: MagicMock) -> int:
    return sum(
        mock.await_count
        for mock in (message.reply_text, message.reply_photo, message.reply_document)
    )


# --- /start and /restart from every phase ------------------------------------------------


@pytest.mark.parametrize("phase", list(Phase))
@pytest.mark.parametrize(
    ("handler", "reply"),
    [
        (gateway.on_start, gateway.NUDGE_SEND_PHOTO),
        (gateway.on_restart, gateway.CLEAN_SLATE),
    ],
)
async def test_commands_wipe_the_session_from_any_phase(
    phase: Phase,
    handler: gateway.Handler,
    reply: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="telegram_documentaries")
    deps = deps_in(phase)
    message = fake_message(text="/restart")
    await handler(fake_update(message), make_context(deps))

    message.reply_text.assert_awaited_once_with(reply)
    session = deps.sessions.get(42)
    assert session == Session(chat_id=42)  # no photo, transcript, dossier or script left
    assert f"from_phase={phase.value}" in caplog.text
    assert "event=session_reset" in caplog.text


async def test_reset_only_affects_the_sender() -> None:
    deps = deps_in(Phase.INTERVIEWING)
    deps.sessions.start_interview(7, PHOTO, "Q?")
    await gateway.on_restart(fake_update(fake_message(text="/restart")), make_context(deps))
    assert deps.sessions.get(7).phase is Phase.INTERVIEWING


async def test_after_restart_a_text_gets_the_photo_nudge() -> None:
    deps = deps_in(Phase.INTERVIEWING)
    await gateway.on_restart(fake_update(fake_message(text="/restart")), make_context(deps))
    message = fake_message(text="my answer")
    await gateway.on_other(fake_update(message), make_context(deps))
    message.reply_text.assert_awaited_once_with(gateway.NUDGE_SEND_PHOTO)


# --- Routing -----------------------------------------------------------------------------------


def command_update(text: str, *, edited: bool = False) -> Update:
    """A command as Telegram really sends it: with a bot_command entity and a bot attached."""
    command = text.split()[0]
    entity = MessageEntity(type=MessageEntity.BOT_COMMAND, offset=0, length=len(command))
    message = real_message(text=text, entities=(entity,))
    message.set_bot(MagicMock(username="documentaries_bot"))
    if edited:
        return Update(update_id=2, edited_message=message)
    return Update(update_id=1, message=message)


@pytest.fixture
def app() -> object:
    return build_application(FAKE_TOKEN, make_deps())


@pytest.mark.parametrize(
    ("text", "callback"),
    [
        ("/start", "on_start"),
        ("/restart", "on_restart"),
        ("/restart now", "on_restart"),
        ("/restart@documentaries_bot", "on_restart"),
    ],
)
def test_commands_route_to_their_handlers(app: object, text: str, callback: str) -> None:
    update = command_update(text)
    assert matching_callbacks(app, update) == [getattr(gateway, callback)]  # type: ignore[arg-type]


def test_other_commands_still_route_to_on_other(app: object) -> None:
    update = command_update("/help")
    assert matching_callbacks(app, update) == [gateway.on_other]  # type: ignore[arg-type]


def test_edited_commands_are_ignored(app: object) -> None:
    update = command_update("/restart", edited=True)
    assert matching_callbacks(app, update) == []  # type: ignore[arg-type]


# --- Command menu ----------------------------------------------------------------------------


async def test_post_init_registers_the_command_menu() -> None:
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock()
    await gateway.register_commands(application)
    application.bot.set_my_commands.assert_awaited_once_with(
        [
            BotCommand("start", gateway.START_DESCRIPTION),
            BotCommand("restart", gateway.RESTART_DESCRIPTION),
        ]
    )


async def test_command_menu_failure_is_logged_not_raised(
    caplog: pytest.LogCaptureFixture,
) -> None:
    application = MagicMock()
    application.bot.set_my_commands = AsyncMock(side_effect=NetworkError("offline"))
    await gateway.register_commands(application)
    assert "event=command_menu_failed" in caplog.text


def test_application_wires_the_command_menu_hook() -> None:
    application = build_application(FAKE_TOKEN, make_deps())
    assert application.post_init is gateway.register_commands


# --- Unexpected errors ---------------------------------------------------------------------------


def error_context(error: Exception) -> MagicMock:
    context = MagicMock()
    context.error = error
    return context


async def test_unexpected_error_is_logged_and_the_user_gets_an_apology(
    caplog: pytest.LogCaptureFixture,
) -> None:
    message = fake_message(text="hi")
    await gateway.log_error(fake_update(message), error_context(RuntimeError("bug!")))
    message.reply_text.assert_awaited_once_with(gateway.SOMETHING_WENT_WRONG)
    assert "/restart" in gateway.SOMETHING_WENT_WRONG
    assert "event=handler_error" in caplog.text
    assert "bug!" in caplog.text


async def test_error_without_a_message_is_only_logged(caplog: pytest.LogCaptureFixture) -> None:
    await gateway.log_error(object(), error_context(RuntimeError("bug!")))
    assert "event=handler_error" in caplog.text


async def test_failing_apology_is_logged_not_raised(caplog: pytest.LogCaptureFixture) -> None:
    message = fake_message(text="hi")
    message.reply_text = AsyncMock(side_effect=NetworkError("down"))
    await gateway.log_error(fake_update(message), error_context(RuntimeError("bug!")))
    assert "event=error_reply_failed" in caplog.text


# --- Media timeouts ------------------------------------------------------------------------------


async def test_photo_download_uses_the_media_timeout() -> None:
    tg_file = telegram_file()
    message = fake_message(photo_size=50_000, tg_file=tg_file)
    await gateway.on_photo(fake_update(message), make_context(make_deps()))

    large = message.photo[-1]
    large.get_file.assert_awaited_once_with(read_timeout=gateway.MEDIA_TRANSFER_TIMEOUT_S)
    tg_file.download_as_bytearray.assert_awaited_once_with(
        read_timeout=gateway.MEDIA_TRANSFER_TIMEOUT_S
    )


def test_media_timeout_is_generous() -> None:
    assert gateway.MEDIA_TRANSFER_TIMEOUT_S >= 60


# --- Sweep: every phase x every kind of input ----------------------------------------------------

INPUTS: dict[str, Callable[[], MagicMock]] = {
    "text": lambda: fake_message(text="hello there"),
    "unknown command": lambda: fake_message(text="/help"),
    "sticker or other non-text": lambda: fake_message(text=None),
    "photo": lambda: fake_message(photo_size=50_000),
    "image file": lambda: fake_message(document_mime="image/png"),
    "non-image file": lambda: fake_message(document_mime="application/pdf"),
}
PHOTO_INPUTS = {"photo", "image file"}  # what filters.PHOTO | filters.Document.IMAGE route


def expected_phase(phase: Phase, kind: str) -> Phase:
    if kind in PHOTO_INPUTS:
        # A photo restarts the documentary, except mid-interview where it gets a nudge.
        return Phase.INTERVIEWING
    if phase in (Phase.INTERVIEW_COMPLETE, Phase.PORTRAIT_DELIVERED, Phase.SCRIPT_READY):
        return Phase.DONE  # any message retries the pending stage, which now succeeds
    return phase


@pytest.mark.parametrize("phase", list(Phase))
@pytest.mark.parametrize("kind", list(INPUTS))
async def test_every_phase_handles_every_input(phase: Phase, kind: str) -> None:
    deps = deps_in(phase)
    message = INPUTS[kind]()
    handler = gateway.on_photo if kind in PHOTO_INPUTS else gateway.on_other

    await handler(fake_update(message), make_context(deps))

    assert replies_of(message) >= 1, "the user must always get an answer"
    assert deps.sessions.get(42).phase is expected_phase(phase, kind)


def test_sweep_covers_every_phase() -> None:
    assert set(SETUPS) == set(Phase)
