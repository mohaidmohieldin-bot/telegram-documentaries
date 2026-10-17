"""Telegram gateway: the only module that talks to python-telegram-bot.

Photos (and images sent as files) go to the Bouncer. A human starts the interview:
each text answer gets exactly one next question until the Interviewer returns the
Dossier, which is shown to the user and stored as the handoff for the next stage.
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
from telegram_documentaries.interviewer import InterviewerError, InterviewerPort, NextQuestion
from telegram_documentaries.session import MAX_ANSWER_CHARS, QA, Dossier, Phase, SessionStore

logger = logging.getLogger(__name__)

DEPS_KEY = "deps"

# --- User-facing replies -------------------------------------------------------------

NUDGE_SEND_PHOTO = "Welcome to The Telegram Documentaries! 🎬 Send me a photo of yourself to begin."
PHOTO_ACCEPTED = (
    "A magnificent specimen! 🦁 You've made it past the Bouncer. "
    "Now for your interview: just answer each question in your own words."
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
INTERVIEWER_UNAVAILABLE_START = (
    "Our interviewer is stuck in traffic. 🚕 Please send your photo again in a moment."
)
INTERVIEWER_UNAVAILABLE = (
    "Our interviewer dropped their notebook. 📓 Please send your answer again in a moment."
)
PORTRAIT_IN_PROGRESS = (
    "Your hybrid portrait is being developed in the lab. 🖼️ "
    "Send a new photo any time to start a fresh documentary."
)


def format_question(number: int, question: str) -> str:
    return f"🎙️ Question {number}: {question}"


def format_nudge(number: int, question: str) -> str:
    return (
        "One thing at a time! 📝 I'm still waiting for your answer to:"
        f"\n\n{format_question(number, question)}"
    )


def format_too_long(number: int, question: str) -> str:
    return (
        f"That's a whole memoir! 📚 Please keep it under {MAX_ANSWER_CHARS} characters."
        f"\n\n{format_question(number, question)}"
    )


def format_finale(dossier: Dossier) -> str:
    quirks = "\n".join(f"• {quirk}" for quirk in dossier.quirks)
    return (
        "🎬 That's a wrap! Here are our field notes:\n\n"
        f"{dossier.profile}\n\n"
        f"Observed quirks:\n{quirks}\n\n"
        f"🐾 Your spirit species: the {dossier.suggested_animal}\n"
        f"{dossier.animal_rationale}\n\n"
        f"{PORTRAIT_IN_PROGRESS}"
    )


# --- Dependencies ------------------------------------------------------------------------


@dataclass(frozen=True)
class Deps:
    bouncer: Bouncer
    interviewer: InterviewerPort
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
    """Photo intake: nudge mid-interview; otherwise Bouncer gate, then the first question."""
    message, chat = update.effective_message, update.effective_chat
    if message is None or chat is None:
        return
    deps = get_deps(context)
    session = deps.sessions.get(chat.id)
    if session.phase is Phase.INTERVIEWING and session.pending_question is not None:
        number = len(session.transcript) + 1
        await message.reply_text(format_nudge(number, session.pending_question))
        return

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
    if not verdict.human_present:
        deps.sessions.reset(chat.id)
        await message.reply_text(BOUNCER_REJECTION)
        return

    try:
        first_question = await deps.interviewer.first_question()
    except InterviewerError as exc:
        logger.error("event=interviewer_failed chat_id=%s turn=1 error=%r", chat.id, exc)
        await message.reply_text(INTERVIEWER_UNAVAILABLE_START)
        return

    deps.sessions.start_interview(chat.id, image, first_question)
    logger.info("event=interview_started chat_id=%s", chat.id)
    await message.reply_text(PHOTO_ACCEPTED)
    await message.reply_text(format_question(1, first_question))


@log_update
async def on_other(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Any non-photo message: an interview answer, or a phase-appropriate nudge."""
    message, chat = update.effective_message, update.effective_chat
    if message is None or chat is None:
        return
    deps = get_deps(context)
    session = deps.sessions.get(chat.id)

    if session.phase is Phase.AWAITING_PHOTO:
        await message.reply_text(NUDGE_SEND_PHOTO)
        return
    if session.phase is Phase.INTERVIEW_COMPLETE or session.pending_question is None:
        await message.reply_text(PORTRAIT_IN_PROGRESS)
        return

    question = session.pending_question
    number = len(session.transcript) + 1
    answer = (message.text or "").strip()
    if not answer or answer.startswith("/"):
        await message.reply_text(format_nudge(number, question))
        return
    if len(answer) > MAX_ANSWER_CHARS:
        await message.reply_text(format_too_long(number, question))
        return

    transcript = (*session.transcript, QA(question=question, answer=answer))
    try:
        step = await deps.interviewer.next_step(transcript)
    except InterviewerError as exc:
        logger.error("event=interviewer_failed chat_id=%s turn=%d error=%r", chat.id, number, exc)
        await message.reply_text(INTERVIEWER_UNAVAILABLE)
        return

    if isinstance(step, NextQuestion):
        deps.sessions.record_answer(chat.id, answer, step.question)
        logger.info("event=interview_answer chat_id=%s answered=%d", chat.id, number)
        await message.reply_text(format_question(number + 1, step.question))
        return

    deps.sessions.complete_interview(chat.id, answer, step)
    logger.info(
        "event=interview_handoff_ready chat_id=%s questions=%d animal=%r",
        chat.id,
        number,
        step.suggested_animal,
    )
    await message.reply_text(format_finale(step))


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
    """Wire the bot: photos and image files to on_photo, other new messages to on_other."""
    app = Application.builder().token(token).build()
    app.bot_data[DEPS_KEY] = deps
    new_message = filters.UpdateType.MESSAGE
    images = filters.PHOTO | filters.Document.IMAGE
    app.add_handler(MessageHandler(new_message & images, on_photo))
    app.add_handler(MessageHandler(new_message, on_other))
    app.add_error_handler(log_error)
    return app
