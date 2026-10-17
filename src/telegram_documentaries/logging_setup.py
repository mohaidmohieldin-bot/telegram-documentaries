"""Process-wide logging configuration (key=value structured lines)."""

import logging

LOG_FORMAT = "%(asctime)s level=%(levelname)s logger=%(name)s %(message)s"


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT, force=True)
    # httpx logs every request URL at INFO; Telegram request URLs embed the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)
