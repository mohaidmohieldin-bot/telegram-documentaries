"""Process-wide logging configuration (key=value structured lines) and stage logging."""

import functools
import logging
import time
from collections.abc import Awaitable, Callable, Coroutine
from typing import Any

LOG_FORMAT = "%(asctime)s level=%(levelname)s logger=%(name)s %(message)s"

logger = logging.getLogger("telegram_documentaries.stages")


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level, format=LOG_FORMAT, force=True)
    # httpx logs every request URL at INFO; Telegram request URLs embed the bot token.
    logging.getLogger("httpx").setLevel(logging.WARNING)


def logged_stage[**P, R](
    stage: str,
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Log a pipeline stage's start, duration and outcome, so stage code stays log-free.

    Failures are logged with their traceback and re-raised unchanged.
    """

    def decorate(func: Callable[P, Awaitable[R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            logger.info("event=stage_started stage=%s", stage)
            started = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
            except Exception as exc:
                duration_ms = round((time.perf_counter() - started) * 1000)
                logger.exception(
                    "event=stage_failed stage=%s duration_ms=%d error=%r", stage, duration_ms, exc
                )
                raise
            duration_ms = round((time.perf_counter() - started) * 1000)
            logger.info("event=stage_done stage=%s duration_ms=%d", stage, duration_ms)
            return result

        return wrapper

    return decorate
