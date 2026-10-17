"""The Bouncer ADK agent: config, message shape, verdict parsing and failure modes.

A fake runner stands in for the ADK Runner, so these tests never call Gemini.
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import cast

import pytest
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from telegram_documentaries.bouncer import (
    BOUNCER_MODEL,
    AdkBouncer,
    BouncerError,
    BouncerVerdict,
    build_bouncer_agent,
)
from telegram_documentaries.media import ImageInput

IMAGE = ImageInput(data=b"\xff\xd8fake-jpeg", mime_type="image/jpeg")
HUMAN_JSON = '{"human_present": true, "reason": "A smiling person faces the camera."}'
NO_HUMAN_JSON = '{"human_present": false, "reason": "A mountain lake at sunset."}'


class FakeEvent:
    def __init__(self, text: str | None, final: bool = True) -> None:
        self.content = (
            types.Content(role="model", parts=[types.Part(text=text)]) if text is not None else None
        )
        self._final = final

    def is_final_response(self) -> bool:
        return self._final


class FakeRunner:
    """Implements the slice of google.adk.runners.Runner that AdkBouncer uses."""

    app_name = "bouncer-test"

    def __init__(
        self,
        events: list[FakeEvent] | None = None,
        error: Exception | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self.session_service = InMemorySessionService()
        self.events = events or []
        self.error = error
        self.delay_s = delay_s
        self.messages: list[types.Content] = []

    async def run_async(
        self, *, user_id: str, session_id: str, new_message: types.Content
    ) -> AsyncGenerator[FakeEvent, None]:
        self.messages.append(new_message)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if self.error:
            raise self.error
        for event in self.events:
            yield event

    async def open_sessions(self) -> int:
        response = await self.session_service.list_sessions(
            app_name=self.app_name, user_id=AdkBouncer.USER_ID
        )
        return len(response.sessions)


def bouncer_with(runner: FakeRunner, timeout_s: float = 5.0) -> AdkBouncer:
    return AdkBouncer(cast(Runner, runner), timeout_s=timeout_s)


# --- Agent configuration -------------------------------------------------------


def test_agent_uses_flash_lite_with_structured_output() -> None:
    agent = build_bouncer_agent()
    assert BOUNCER_MODEL == "gemini-3.1-flash-lite"
    assert agent.model == BOUNCER_MODEL
    assert agent.output_schema is BouncerVerdict
    assert "human" in str(agent.instruction).lower()


# --- Message shape ----------------------------------------------------------------


async def test_sends_image_bytes_and_mime_type_to_the_model() -> None:
    runner = FakeRunner([FakeEvent(HUMAN_JSON)])
    await bouncer_with(runner).check(IMAGE)

    (message,) = runner.messages
    assert message.role == "user"
    blobs = [p.inline_data for p in message.parts or [] if p.inline_data]
    assert len(blobs) == 1
    assert blobs[0].data == IMAGE.data
    assert blobs[0].mime_type == "image/jpeg"


# --- Verdicts ---------------------------------------------------------------------


async def test_person_photo_gives_human_verdict() -> None:
    verdict = await bouncer_with(FakeRunner([FakeEvent(HUMAN_JSON)])).check(IMAGE)
    assert verdict == BouncerVerdict(
        human_present=True, reason="A smiling person faces the camera."
    )


async def test_landscape_photo_gives_no_human_verdict() -> None:
    verdict = await bouncer_with(FakeRunner([FakeEvent(NO_HUMAN_JSON)])).check(IMAGE)
    assert verdict.human_present is False


async def test_only_the_final_response_is_used() -> None:
    runner = FakeRunner([FakeEvent("thinking...", final=False), FakeEvent(NO_HUMAN_JSON)])
    verdict = await bouncer_with(runner).check(IMAGE)
    assert verdict.human_present is False


# --- Failure modes ------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Yes, there is a human.",  # prose instead of JSON
        '{"human_present": "maybe", "reason": "?"}',  # wrong type
        '{"reason": "missing verdict"}',  # missing field
        '{"human_present": true, "reason": "' + "x" * 301 + '"}',  # reason too long
        "",
    ],
)
async def test_invalid_model_output_raises_bouncer_error(text: str) -> None:
    with pytest.raises(BouncerError):
        await bouncer_with(FakeRunner([FakeEvent(text)])).check(IMAGE)


async def test_no_final_response_raises_bouncer_error() -> None:
    with pytest.raises(BouncerError):
        await bouncer_with(FakeRunner([FakeEvent("partial", final=False)])).check(IMAGE)


async def test_final_event_without_content_raises_bouncer_error() -> None:
    with pytest.raises(BouncerError):
        await bouncer_with(FakeRunner([FakeEvent(None)])).check(IMAGE)


async def test_runner_exception_raises_bouncer_error() -> None:
    runner = FakeRunner(error=ConnectionError("network down"))
    with pytest.raises(BouncerError) as excinfo:
        await bouncer_with(runner).check(IMAGE)
    assert isinstance(excinfo.value.__cause__, ConnectionError)


async def test_timeout_raises_bouncer_error() -> None:
    runner = FakeRunner([FakeEvent(HUMAN_JSON)], delay_s=1.0)
    with pytest.raises(BouncerError, match="timed out"):
        await bouncer_with(runner, timeout_s=0.05).check(IMAGE)


# --- Throwaway ADK sessions ------------------------------------------------------------


async def test_adk_session_is_deleted_after_success() -> None:
    runner = FakeRunner([FakeEvent(HUMAN_JSON)])
    await bouncer_with(runner).check(IMAGE)
    assert await runner.open_sessions() == 0


async def test_adk_session_is_deleted_after_failure() -> None:
    runner = FakeRunner(error=RuntimeError("boom"))
    with pytest.raises(BouncerError):
        await bouncer_with(runner).check(IMAGE)
    assert await runner.open_sessions() == 0


async def test_repeated_checks_do_not_leak_sessions() -> None:
    runner = FakeRunner([FakeEvent(HUMAN_JSON)])
    bouncer = bouncer_with(runner)
    for _ in range(3):
        await bouncer.check(IMAGE)
    assert await runner.open_sessions() == 0
