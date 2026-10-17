"""Logging is configured once and never leaks the bot token."""

import logging

from telegram_documentaries.logging_setup import configure_logging


def test_http_client_request_logs_are_silenced() -> None:
    # httpx logs full request URLs at INFO, and Telegram URLs contain the bot token.
    configure_logging()
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_project_logs_at_info() -> None:
    configure_logging()
    assert logging.getLogger("telegram_documentaries").isEnabledFor(logging.INFO)
