"""Gateway routing: photos go to the Bouncer, everything else gets a phase-based reply."""

import logging
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Document, Message, PhotoSize, Update
from telegram.error import NetworkError
from telegram.ext import Application, BaseHandler

from telegram_documentaries import gateway
from telegram_documentaries.bouncer import BouncerError, BouncerVerdict
from telegram_documentaries.gateway import DEPS_KEY, Deps, build_application
from telegram_documentaries.media import MAX_IMAGE_BYTES, ImageInput
from telegram_documentaries.session import Phase, SessionStore

FAKE_TOKEN = "123456789:AAH-fake-token-for-tests"
PHOTO_BYTES = b"\xff\xd8person-or-landscape"

HUMAN = BouncerVerdict(human_present=True, reason="A person smiling.")
NO_HUMAN = BouncerVerdict(human_present=False, reason="A mountain landscape.")


class FakeBouncer:
    def __init__(self, verdict: BouncerVerdict | None = HUMAN, error: Exception | None = None):
        self.verdict = verdict
        self.error = error
        self.images: list[ImageInput] = []

    async def check(self, image: ImageInput) -> BouncerVerdict:
        self.images.append(image)
        if self.error:
            raise self.error
        assert self.verdict is not None
        return self.verdict


# --- Fake Telegram objects ------------------------------------------------------


def telegram_file(data: bytes = PHOTO_BYTES, error: Exception | None = None) -> MagicMock:
    tg_file = MagicMock()
    tg_file.download_as_bytearray = AsyncMock(
        return_value=bytearray(data), side_effect=error
    )
    return tg_file


def fake_message(
    *,
    photo_size: int | None = None,
    document_mime: str | None = None,
    document_size: int = 1_000,
    tg_file: MagicMock | None = None,
) -> MagicMock:
    message = MagicMock()
    message.reply_text = AsyncMock()
    message.photo = ()
    message.document = None
    tg_file = tg_file or telegram_file()
    if photo_size is not None:
        small = MagicMock(file_size=100, get_file=AsyncMock(return_value=telegram_file(b"tiny")))
        large = MagicMock(file_size=photo_size, get_file=AsyncMock(return_value=tg_file))
        message.photo = (small, large)  # Telegram lists sizes smallest first
    if document_mime is not None:
        message.document = MagicMock(
            mime_type=document_mime,
            file_size=document_size,
            get_file=AsyncMock(return_value=tg_file),
        )
    return message


def fake_update(message: MagicMock | None, chat_id: int = 42) -> MagicMock:
    update = MagicMock(spec=Update)
    update.update_id = 1
    update.effective_message = message
    update.effective_chat = MagicMock(id=chat_id) if message is not None else None
    return update


def make_context(deps: Deps) -> MagicMock:
    context = MagicMock()
    context.bot_data = {DEPS_KEY: deps}
    return context


def make_deps(bouncer: FakeBouncer | None = None) -> Deps:
    return Deps(bouncer=bouncer or FakeBouncer(), sessions=SessionStore())


def replied(message: MagicMock) -> str:
    message.reply_text.assert_awaited_once()
    return str(message.reply_text.await_args.args[0])


# --- Text and other non-photo messages ------------------------------------------------


async def test_text_before_photo_gets_nudge_without_calling_bouncer() -> None:
    bouncer = FakeBouncer()
    deps = make_deps(bouncer)
    message = fake_message()
    await gateway.on_other(fake_update(message), make_context(deps))
    assert replied(message) == gateway.NUDGE_SEND_PHOTO
    assert bouncer.images == []


async def test_text_after_acceptance_gets_youre_in_reply() -> None:
    deps = make_deps()
    deps.sessions.set_phase(42, Phase.PHOTO_ACCEPTED)
    message = fake_message()
    await gateway.on_other(fake_update(message), make_context(deps))
    assert replied(message) == gateway.ALREADY_ACCEPTED


# --- Bouncer: positive and negative ----------------------------------------------------


async def test_person_photo_is_accepted() -> None:
    bouncer = FakeBouncer(HUMAN)
    deps = make_deps(bouncer)
    message = fake_message(photo_size=50_000)
    await gateway.on_photo(fake_update(message), make_context(deps))

    assert replied(message) == gateway.PHOTO_ACCEPTED
    assert deps.sessions.get(42).phase is Phase.PHOTO_ACCEPTED
    assert bouncer.images == [ImageInput(data=PHOTO_BYTES, mime_type="image/jpeg")]


async def test_landscape_photo_is_rejected_cheekily() -> None:
    deps = make_deps(FakeBouncer(NO_HUMAN))
    message = fake_message(photo_size=50_000)
    await gateway.on_photo(fake_update(message), make_context(deps))

    reply = replied(message)
    assert reply == gateway.BOUNCER_REJECTION
    assert "human" in reply.lower()
    assert deps.sessions.get(42).phase is Phase.AWAITING_PHOTO


async def test_rejection_resets_a_previously_accepted_session() -> None:
    deps = make_deps(FakeBouncer(NO_HUMAN))
    deps.sessions.set_phase(42, Phase.PHOTO_ACCEPTED)
    await gateway.on_photo(fake_update(fake_message(photo_size=50_000)), make_context(deps))
    assert deps.sessions.get(42).phase is Phase.AWAITING_PHOTO


async def test_largest_photo_size_is_downloaded() -> None:
    bouncer = FakeBouncer()
    await gateway.on_photo(
        fake_update(fake_message(photo_size=50_000)), make_context(make_deps(bouncer))
    )
    assert bouncer.images[0].data == PHOTO_BYTES  # not the b"tiny" thumbnail


async def test_png_sent_as_file_is_checked_as_png() -> None:
    bouncer = FakeBouncer(HUMAN)
    message = fake_message(document_mime="image/png")
    await gateway.on_photo(fake_update(message), make_context(make_deps(bouncer)))
    assert bouncer.images[0].mime_type == "image/png"
    assert replied(message) == gateway.PHOTO_ACCEPTED


# --- Graceful degradation (no state change, friendly reply) -------------------------------


async def test_unsupported_image_type_is_refused_before_bouncer() -> None:
    bouncer = FakeBouncer()
    deps = make_deps(bouncer)
    message = fake_message(document_mime="image/gif")
    await gateway.on_photo(fake_update(message), make_context(deps))
    assert replied(message) == gateway.UNSUPPORTED_IMAGE
    assert bouncer.images == []


async def test_oversized_photo_is_refused_without_downloading() -> None:
    bouncer = FakeBouncer()
    tg_file = telegram_file()
    message = fake_message(photo_size=MAX_IMAGE_BYTES + 1, tg_file=tg_file)
    await gateway.on_photo(fake_update(message), make_context(make_deps(bouncer)))
    assert replied(message) == gateway.PHOTO_TOO_LARGE
    tg_file.download_as_bytearray.assert_not_awaited()
    assert bouncer.images == []


async def test_download_failure_gets_friendly_reply(caplog: pytest.LogCaptureFixture) -> None:
    bouncer = FakeBouncer()
    deps = make_deps(bouncer)
    deps.sessions.set_phase(42, Phase.PHOTO_ACCEPTED)
    message = fake_message(photo_size=50_000, tg_file=telegram_file(error=NetworkError("down")))
    await gateway.on_photo(fake_update(message), make_context(deps))

    assert replied(message) == gateway.PHOTO_DOWNLOAD_FAILED
    assert bouncer.images == []
    assert deps.sessions.get(42).phase is Phase.PHOTO_ACCEPTED
    assert "event=photo_download_failed" in caplog.text


async def test_empty_download_is_treated_as_failure() -> None:
    message = fake_message(photo_size=50_000, tg_file=telegram_file(b""))
    await gateway.on_photo(fake_update(message), make_context(make_deps()))
    assert replied(message) == gateway.PHOTO_DOWNLOAD_FAILED


async def test_bouncer_failure_gets_friendly_reply(caplog: pytest.LogCaptureFixture) -> None:
    deps = make_deps(FakeBouncer(error=BouncerError("timed out")))
    deps.sessions.set_phase(42, Phase.PHOTO_ACCEPTED)
    message = fake_message(photo_size=50_000)
    await gateway.on_photo(fake_update(message), make_context(deps))

    assert replied(message) == gateway.BOUNCER_UNAVAILABLE
    assert deps.sessions.get(42).phase is Phase.PHOTO_ACCEPTED
    assert "event=bouncer_failed" in caplog.text


async def test_update_without_message_is_ignored() -> None:
    bouncer = FakeBouncer()
    await gateway.on_photo(fake_update(None), make_context(make_deps(bouncer)))
    await gateway.on_other(fake_update(None), make_context(make_deps(bouncer)))
    assert bouncer.images == []


# --- Isolation and logging -------------------------------------------------------------------


async def test_chats_are_isolated() -> None:
    deps = make_deps(FakeBouncer(HUMAN))
    await gateway.on_photo(fake_update(fake_message(photo_size=1), chat_id=1), make_context(deps))
    other = fake_message()
    await gateway.on_other(fake_update(other, chat_id=2), make_context(deps))
    assert deps.sessions.get(1).phase is Phase.PHOTO_ACCEPTED
    assert replied(other) == gateway.NUDGE_SEND_PHOTO


async def test_verdict_is_logged_with_chat_id(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="telegram_documentaries")
    deps = make_deps(FakeBouncer(NO_HUMAN))
    await gateway.on_photo(
        fake_update(fake_message(photo_size=1), chat_id=777), make_context(deps)
    )
    assert "event=bouncer_verdict" in caplog.text
    assert "chat_id=777" in caplog.text
    assert "human_present=False" in caplog.text
    assert "person-or-landscape" not in caplog.text  # image bytes never logged


# --- Application routing (real Telegram objects) ------------------------------------------------


def real_message(**kwargs: object) -> Message:
    return Message(
        message_id=1,
        date=datetime.now(UTC),
        chat=Chat(id=42, type=Chat.PRIVATE),
        **kwargs,  # type: ignore[arg-type]
    )


def matching_callbacks(app: Application, update: Update) -> list[object]:  # type: ignore[type-arg]
    """Callbacks of the handlers that would receive this update (first match per group)."""
    callbacks = []
    for group in app.handlers.values():
        handler: BaseHandler  # type: ignore[type-arg]
        for handler in group:
            if handler.check_update(update):
                callbacks.append(handler.callback)
                break
    return callbacks


@pytest.fixture
def app() -> Application:  # type: ignore[type-arg]
    return build_application(FAKE_TOKEN, make_deps())


def test_photo_routes_to_photo_handler(app: Application) -> None:  # type: ignore[type-arg]
    photo = PhotoSize(file_id="f", file_unique_id="u", width=10, height=10)
    update = Update(update_id=1, message=real_message(photo=(photo,)))
    assert matching_callbacks(app, update) == [gateway.on_photo]


def test_image_document_routes_to_photo_handler(app: Application) -> None:  # type: ignore[type-arg]
    doc = Document(file_id="f", file_unique_id="u", mime_type="image/png")
    update = Update(update_id=1, message=real_message(document=doc))
    assert matching_callbacks(app, update) == [gateway.on_photo]


@pytest.mark.parametrize("text", ["hi", "/start", "🦁"])
def test_text_routes_to_other_handler(app: Application, text: str) -> None:  # type: ignore[type-arg]
    update = Update(update_id=1, message=real_message(text=text))
    assert matching_callbacks(app, update) == [gateway.on_other]


def test_edited_messages_are_ignored(app: Application) -> None:  # type: ignore[type-arg]
    update = Update(update_id=2, edited_message=real_message(text="edited"))
    assert matching_callbacks(app, update) == []


def test_application_registers_an_error_handler(app: Application) -> None:  # type: ignore[type-arg]
    assert app.error_handlers


def test_application_stores_deps(app: Application) -> None:  # type: ignore[type-arg]
    assert isinstance(app.bot_data[DEPS_KEY], Deps)
