"""Logging is configured once, never leaks the bot token, and stages log via a decorator."""

import logging

import pytest

from telegram_documentaries.logging_setup import configure_logging, logged_stage


def test_http_client_request_logs_are_silenced() -> None:
    # httpx logs full request URLs at INFO, and Telegram URLs contain the bot token.
    configure_logging()
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_project_logs_at_info() -> None:
    configure_logging()
    assert logging.getLogger("telegram_documentaries").isEnabledFor(logging.INFO)


async def test_logged_stage_logs_start_and_success(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="telegram_documentaries")

    @logged_stage("demo")
    async def double(x: int) -> int:
        return x * 2

    assert await double(21) == 42
    assert "event=stage_started stage=demo" in caplog.text
    assert "event=stage_done stage=demo" in caplog.text
    assert "duration_ms=" in caplog.text


async def test_logged_stage_logs_failure_and_reraises(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="telegram_documentaries")
    boom = ValueError("boom")

    @logged_stage("demo")
    async def fail() -> None:
        raise boom

    with pytest.raises(ValueError) as excinfo:
        await fail()
    assert excinfo.value is boom
    assert "event=stage_failed stage=demo" in caplog.text
    assert "boom" in caplog.text
    assert "event=stage_done" not in caplog.text


async def test_logged_stage_preserves_function_name() -> None:
    @logged_stage("demo")
    async def named() -> None:
        return None

    assert named.__name__ == "named"
