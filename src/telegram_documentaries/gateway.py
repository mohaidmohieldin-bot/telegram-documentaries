"""Telegram gateway: the only module that talks to python-telegram-bot.

Phase 1 behaviour: every new message gets the same hardcoded reply.
"""

import functools
import logging
from collections.abc import Awaitable, Callable

from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters

logger = logging.getLogger(__name__)

REPLY_TEXT = "hey mate!"

Handler = Callable[[Update, ContextTypes.DEFAULT_TYPE], Awaitable[None]]


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


@log_update
async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Reply to any message with the fixed greeting."""
    message = update.effective_message
    if message is None:
        return
    await message.reply_text(REPLY_TEXT)


async def log_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log any exception raised while handling an update, loudly and with context."""
    update_id = update.update_id if isinstance(update, Update) else None
    logger.error(
        "event=handler_error update_id=%s error=%r",
        update_id,
        context.error,
        exc_info=context.error,
    )


def build_application(token: str) -> Application:  # type: ignore[type-arg]
    """Wire the bot: reply to every new (non-edited) message, log every error."""
    app = Application.builder().token(token).build()
    app.add_handler(MessageHandler(filters.UpdateType.MESSAGE, reply))
    app.add_error_handler(log_error)
    return app
