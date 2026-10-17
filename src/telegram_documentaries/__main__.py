"""Entrypoint: `uv run telegram-documentaries` or `uv run python -m telegram_documentaries`."""

import logging
import sys

from pydantic import ValidationError
from telegram import Update

from telegram_documentaries.config import Settings
from telegram_documentaries.gateway import build_application
from telegram_documentaries.logging_setup import configure_logging

logger = logging.getLogger("telegram_documentaries")


def main() -> None:
    configure_logging()
    try:
        settings = Settings()
    except ValidationError as exc:
        # include_input=False: never echo a (possibly real) token into the logs.
        for error in exc.errors(include_input=False, include_url=False):
            field = ".".join(str(part) for part in error["loc"]) or "settings"
            logger.error("event=config_invalid field=%s reason=%r", field, error["msg"])
        logger.error("event=startup_aborted hint=%r", "copy .env.example to .env and fill it in")
        sys.exit(1)

    app = build_application(settings.telegram_bot_token.get_secret_value())
    logger.info("event=bot_starting transport=long_polling")
    app.run_polling(allowed_updates=[Update.MESSAGE])


if __name__ == "__main__":
    main()
