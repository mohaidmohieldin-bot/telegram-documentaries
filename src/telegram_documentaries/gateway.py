"""Telegram gateway: the only module that talks to python-telegram-bot.

Photos (and images sent as files) go to the Bouncer; every other new message gets a
reply based on the chat's session phase.
"""

import functools
import logging
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from telegram import File, Message, Update
from telegram.error import TelegramError
from telegram.ext import Application, ContextTypes, MessageHandler, filters

from telegram_documentaries.bouncer import Bouncer, BouncerError
from telegram_documentaries.media import MAX_IMAGE_BYTES, SUPPORTED_IMAGE_TYPES, ImageInput
from telegram_documentaries.session import Phase, SessionStore

logger = logging.getLogger(__name__)

DEPS_KEY = "deps"

# --- User-facing replies -------------------------------------------------------------

NUDGE_SEND_PHOTO = "Welcome to The Telegram Documentaries! 🎬 Send me a photo of yourself to begin."
PHOTO_ACCEPTED = (
    "A magnificent specimen! 🦁 You've made it past the Bouncer. Your interview begins soon."
)
ALREADY_ACCEPTED = (
    "You're in! 🎟️ The interview is still being filmed. "
    "Send another photo if you'd like to start over."
)
BOUNCER_REJECTION = (
    "🚫 Sorry, this is a documentary about HUMANS. I see no human here: no face, no body, "
    "not even a suspicious elbow. Our nature crew only films people, so please send a "
    "photo with a real human in it."
)
BOUNCER_UNAVAILABLE = (
    "Our Bouncer has wandered off for a tea break. ☕ Please send your photo again in a moment."
)
PHOTO_TOO_LARGE = "That photo is too big for me (20 MB max). Please send a smaller one. 📏"
UNSUPPORTED_IMAGE = "I can't read that image format. Please send a JPG or PNG photo. 🖼️"
PHOTO_DOWNLOAD_FAILED = "I couldn't fetch your photo from Telegram. Please try sending it again."


# --- Dependencies ------------------------------------------------------------------------


@dataclass(frozen=True)
class Deps:
    bouncer: Bouncer
    sessions: SessionStore


def get_deps(context: ContextTypes.DEFAULT_TYPE) -> Deps:
    deps = context.bot_data[DEPS_KEY]
    if not isinstance(deps, Deps):
        raise TypeError(f"bot_data[{DEPS_KEY!r}] is {type(deps).__name__}, expected Deps")
    return deps


# --- Logging decorator ---------------------------------------------------------------------

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Coroutine[Any, Any, None]]


def log_update(handler: Handler) -> Handler:
    """Log every update a handler receives, keeping logging out of the handler body."""

    @functools.wraps(handler)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        chat_id = update.effective_chat.id if update.effective_chat else None
        logger.info(
            "event=update_received handler=%s update_id=%s chat_id=%s",
            getattr(handler, "__name__", "handler"),
            update.update_id,
            chat_id,
        )
        await handler(update, context)

    return wrapper


# --- Photo download ------------------------------------------------------------------------


class PhotoTooLarge(Exception):
    pass


class UnsupportedImage(Exception):
    pass


async def download_image(message: Message) -> ImageInput:
    """Download the photo (largest size) or image document as a validated ImageInput.

    Raises PhotoTooLarge / UnsupportedImage before downloading, TelegramError if the
    download fails, and ValidationError if the downloaded bytes break the contract.
    """
    get_file: Callable[[], Awaitable[File]]
    file_size: int | None
    mime_type: str
    if message.photo:
        source = message.photo[-1]  # Telegram lists sizes smallest first
        mime_type = "image/jpeg"  # Telegram re-encodes compressed photos as JPEG
        file_size = source.file_size
        get_file = source.get_file
    elif message.document:
        mime_type = message.document.mime_type or ""
        if mime_type not in SUPPORTED_IMAGE_TYPES:
            raise UnsupportedImage(mime_type)
        file_size = message.document.file_size
        get_file = message.document.get_file
    else:
        raise UnsupportedImage("no photo or document")

    if file_size is not None and file_size > MAX_IMAGE_BYTES:
        raise PhotoTooLarge(file_size)

    tg_file = await get_file()
    data = bytes(await tg_file.download_as_bytearray())
    return ImageInput.model_validate({"data": data, "mime_type": mime_type})


# --- Handlers -------------------------------------------------------------------------------


@log_update
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Bouncer gate: accept photos with a human, reset and reject everything else."""
    message, chat = update.effective_message, update.effective_chat
    if message is None or chat is None:
        return
    deps = get_deps(context)

    try:
        image = await download_image(message)
    except UnsupportedImage as exc:
        logger.warning("event=unsupported_image chat_id=%s mime_type=%r", chat.id, str(exc))
        await message.reply_text(UNSUPPORTED_IMAGE)
        return
    except PhotoTooLarge as exc:
        logger.warning("event=photo_too_large chat_id=%s file_size=%s", chat.id, exc.args[0])
        await message.reply_text(PHOTO_TOO_LARGE)
        return
    except (TelegramError, ValidationError) as exc:
        logger.error(
            "event=photo_download_failed chat_id=%s error=%s",
            chat.id,
            type(exc).__name__,
            exc_info=exc,
        )
        await message.reply_text(PHOTO_DOWNLOAD_FAILED)
        return

    try:
        verdict = await deps.bouncer.check(image)
    except BouncerError as exc:
        logger.error("event=bouncer_failed chat_id=%s error=%r", chat.id, exc, exc_info=exc)
        await message.reply_text(BOUNCER_UNAVAILABLE)
        return

    logger.info(
        "event=bouncer_verdict chat_id=%s human_present=%s reason=%r",
        chat.id,
        verdict.human_present,
        verdict.reason,
    )
    if verdict.human_present:
        deps.sessions.set_phase(chat.id, Phase.PHOTO_ACCEPTED)
        await message.reply_text(PHOTO_ACCEPTED)
    else:
        deps.sessions.reset(chat.id)
        await message.reply_text(BOUNCER_REJECTION)


@log_update
async def on_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Any non-photo message: tell the user what the bot expects in this phase."""
    message, chat = update.effective_message, update.effective_chat
    if message is None or chat is None:
        return
    phase = get_deps(context).sessions.get(chat.id).phase
    reply = ALREADY_ACCEPTED if phase is Phase.PHOTO_ACCEPTED else NUDGE_SEND_PHOTO
    await message.reply_text(reply)


async def log_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log any exception raised while handling an update, loudly and with context."""
    update_id = update.update_id if isinstance(update, Update) else None
    logger.error(
        "event=handler_error update_id=%s error=%r",
        update_id,
        context.error,
        exc_info=context.error,
    )


def build_application(token: str, deps: Deps) -> Application:  # type: ignore[type-arg]
    """Wire the bot: photos to the Bouncer, other new messages to on_other."""
    app = Application.builder().token(token).build()
    app.bot_data[DEPS_KEY] = deps
    new_message = filters.UpdateType.MESSAGE
    images = filters.PHOTO | filters.Document.IMAGE
    app.add_handler(MessageHandler(new_message & images, on_photo))
    app.add_handler(MessageHandler(new_message, on_other))
    app.add_error_handler(log_error)
    return app
