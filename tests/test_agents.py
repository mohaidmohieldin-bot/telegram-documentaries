"""Shared ADK caller: structured output, failure modes, throwaway sessions."""

import contextlib

import pytest
from google.genai import types
from pydantic import BaseModel

from telegram_documentaries.agents import AgentCallError, run_structured_agent
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
