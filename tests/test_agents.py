"""Shared ADK caller: structured output, failure modes, throwaway sessions."""

import contextlib

import pytest
from google.genai import types
from pydantic import BaseModel

from telegram_documentaries.agents import AgentCallError, run_image_agent, run_structured_agent
from telegram_documentaries.media import PortraitImage
from tests.adk_fakes import FakeEvent, FakeRunner

USER_ID = "tester"
PARTS = [types.Part(text="hello")]


class Answer(BaseModel):
    value: int


class DemoError(AgentCallError):
    pass


async def call(runner: FakeRunner, timeout_s: float = 5.0) -> Answer:
    return await run_structured_agent(
        runner.as_runner(),
        user_id=USER_ID,
        parts=PARTS,
        schema=Answer,
        error=DemoError,
        timeout_s=timeout_s,
    )


async def test_parses_structured_output() -> None:
    assert await call(FakeRunner.replying('{"value": 42}')) == Answer(value=42)


async def test_sends_parts_as_a_user_message() -> None:
    runner = FakeRunner.replying('{"value": 1}')
    await call(runner)
    (message,) = runner.messages
    assert message.role == "user"
    assert runner.sent_text() == "hello"


async def test_uses_only_the_final_response() -> None:
    runner = FakeRunner([FakeEvent("draft", final=False), FakeEvent('{"value": 7}')])
    assert (await call(runner)).value == 7


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ([FakeEvent(None, error_code="403", error_message="key leaked")], "403.*key leaked"),
        ([FakeEvent("partial", final=False)], "without a final response"),
        ([FakeEvent(None)], "no content"),
        ([FakeEvent("not json")], "did not match Answer"),
        ([FakeEvent('{"value": "seven"}')], "did not match Answer"),
        (ConnectionError("network down"), "model call failed"),
    ],
)
async def test_failures_raise_the_given_error_type(
    response: list[FakeEvent] | Exception, message: str
) -> None:
    with pytest.raises(DemoError, match=message):
        await call(FakeRunner(response))


async def test_timeout_raises_the_given_error_type() -> None:
    runner = FakeRunner([FakeEvent('{"value": 1}')], delay_s=1.0)
    with pytest.raises(DemoError, match="timed out"):
        await call(runner, timeout_s=0.05)


async def test_unexpected_exception_keeps_its_cause() -> None:
    with pytest.raises(DemoError) as excinfo:
        await call(FakeRunner(ConnectionError("down")))
    assert isinstance(excinfo.value.__cause__, ConnectionError)


@pytest.mark.parametrize(
    "response", [[FakeEvent('{"value": 1}')], [FakeEvent("bad")], RuntimeError("boom")]
)
async def test_throwaway_session_is_always_deleted(response: list[FakeEvent] | Exception) -> None:
    runner = FakeRunner(response)
    with contextlib.suppress(DemoError):
        await call(runner)
    assert await runner.open_sessions(USER_ID) == 0


# --- Image output ----------------------------------------------------------------------

PNG = b"\x89PNG\r\n\x1a\nfake-portrait"


def image_part(data: bytes = PNG, mime: str = "image/png") -> types.Part:
    return types.Part.from_bytes(data=data, mime_type=mime)


async def call_image(runner: FakeRunner, timeout_s: float = 5.0) -> PortraitImage:
    return await run_image_agent(
        runner.as_runner(), user_id=USER_ID, parts=PARTS, error=DemoError, timeout_s=timeout_s
    )


async def test_image_agent_returns_the_generated_image() -> None:
    runner = FakeRunner([FakeEvent(None, parts=[types.Part(text="Here you go!"), image_part()])])
    assert await call_image(runner) == PortraitImage(data=PNG, mime_type="image/png")


async def test_image_agent_returns_the_first_image_only() -> None:
    parts = [image_part(b"first", "image/jpeg"), image_part(b"second")]
    portrait = await call_image(FakeRunner([FakeEvent(None, parts=parts)]))
    assert (portrait.data, portrait.mime_type) == (b"first", "image/jpeg")


async def test_text_only_answer_raises_with_the_model_text() -> None:
    refusal = FakeEvent("I can't edit photos of real people in that way.")
    with pytest.raises(DemoError, match="no image.*can't edit photos"):
        await call_image(FakeRunner([refusal]))


async def test_overlong_refusal_text_is_truncated() -> None:
    with pytest.raises(DemoError) as excinfo:
        await call_image(FakeRunner([FakeEvent("blah " * 500)]))
    assert len(str(excinfo.value)) < 400


async def test_unsupported_generated_image_type_raises() -> None:
    gif = FakeEvent(None, parts=[image_part(b"GIF89a", "image/gif")])
    with pytest.raises(DemoError, match="did not match PortraitImage"):
        await call_image(FakeRunner([gif]))


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ([FakeEvent(None, error_code="SAFETY", error_message="blocked")], "SAFETY.*blocked"),
        ([FakeEvent(None)], "no content"),
        (ConnectionError("down"), "model call failed"),
    ],
)
async def test_image_agent_shares_failure_handling(
    response: list[FakeEvent] | Exception, message: str
) -> None:
    runner = FakeRunner(response)
    with pytest.raises(DemoError, match=message):
        await call_image(runner)
    assert await runner.open_sessions(USER_ID) == 0


async def test_image_agent_timeout() -> None:
    runner = FakeRunner([FakeEvent(None, parts=[image_part()])], delay_s=1.0)
    with pytest.raises(DemoError, match="timed out"):
        await call_image(runner, timeout_s=0.05)
