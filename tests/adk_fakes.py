"""Fakes for the slice of google.adk.runners.Runner our stages use (no network)."""

import asyncio
from collections.abc import AsyncGenerator
from typing import cast

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types


class FakeEvent:
    def __init__(
        self,
        text: str | None,
        final: bool = True,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.content = (
            types.Content(role="model", parts=[types.Part(text=text)]) if text is not None else None
        )
        self._final = final
        self.error_code = error_code
        self.error_message = error_message

    def is_final_response(self) -> bool:
        return self._final


Response = list[FakeEvent] | Exception


class FakeRunner:
    """Replays one scripted response per run_async call and records every message sent."""

    app_name = "fake-app"

    def __init__(self, *responses: Response, delay_s: float = 0.0) -> None:
        self.session_service = InMemorySessionService()
        self._responses = list(responses)
        self.delay_s = delay_s
        self.messages: list[types.Content] = []

    @classmethod
    def replying(cls, *texts: str) -> "FakeRunner":
        """A runner whose successive calls each return one final text response."""
        return cls(*([FakeEvent(text)] for text in texts))

    @property
    def calls(self) -> int:
        return len(self.messages)

    def as_runner(self) -> Runner:
        return cast(Runner, self)

    async def run_async(
        self, *, user_id: str, session_id: str, new_message: types.Content
    ) -> AsyncGenerator[FakeEvent, None]:
        self.messages.append(new_message)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if not self._responses:
            raise AssertionError("FakeRunner called more times than scripted")
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        for event in response:
            yield event

    async def open_sessions(self, user_id: str) -> int:
        listed = await self.session_service.list_sessions(app_name=self.app_name, user_id=user_id)
        return len(listed.sessions)

    def sent_text(self, call: int = -1) -> str:
        """All text parts of the message sent on the given call."""
        parts = self.messages[call].parts or []
        return "".join(part.text or "" for part in parts)
