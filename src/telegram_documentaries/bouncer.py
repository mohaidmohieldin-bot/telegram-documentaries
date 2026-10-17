"""The Bouncer: a Google ADK vision agent that checks a photo contains a human.

Stateless: each check runs in a throwaway ADK session that is deleted afterwards.
Our own SessionStore remains the single source of truth for conversation state.
"""

import asyncio
from typing import ClassVar, Protocol

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field, ValidationError

from telegram_documentaries.logging_setup import logged_stage
from telegram_documentaries.media import ImageInput

BOUNCER_MODEL = "gemini-3.1-flash-lite"
BOUNCER_TIMEOUT_S = 30.0
APP_NAME = "telegram_documentaries_bouncer"

BOUNCER_INSTRUCTION = """\
You are the Bouncer for a comedy wildlife-documentary bot. You will be shown one image.

Decide whether it contains a real, discernible human: a human face or a human body
(a selfie, portrait, group photo or full-body shot all count, even if partly visible).

These do NOT count as a human: drawings, cartoons, paintings, statues, dolls, toys,
mannequins, animals and pets, landscapes, objects, food, screenshots of text, or an image
too dark or blurry to make anyone out.

Respond only with JSON matching the schema: set "human_present" to true or false, and give
a one-sentence "reason" describing what you see.
"""


class BouncerVerdict(BaseModel):
    """The Bouncer's structured decision. `reason` is for logs, never shown to users."""

    human_present: bool = Field(description="True if a real, discernible human is present.")
    reason: str = Field(max_length=300, description="One sentence describing the image.")


class BouncerError(Exception):
    """The Bouncer could not reach a valid verdict (timeout, API error, bad output)."""


class Bouncer(Protocol):
    async def check(self, image: ImageInput) -> BouncerVerdict: ...


def build_bouncer_agent(model: str = BOUNCER_MODEL) -> LlmAgent:
    return LlmAgent(
        name="bouncer",
        model=model,
        description="Checks that a submitted photo contains a real human.",
        instruction=BOUNCER_INSTRUCTION,
        output_schema=BouncerVerdict,
    )


class AdkBouncer:
    """Runs the Bouncer agent through an ADK Runner and validates its verdict."""

    USER_ID: ClassVar[str] = "bouncer"

    def __init__(self, runner: Runner, timeout_s: float = BOUNCER_TIMEOUT_S) -> None:
        self._runner = runner
        self._timeout_s = timeout_s

    @logged_stage("bouncer")
    async def check(self, image: ImageInput) -> BouncerVerdict:
        sessions = self._runner.session_service
        session = await sessions.create_session(
            app_name=self._runner.app_name, user_id=self.USER_ID
        )
        try:
            text = await asyncio.wait_for(
                self._final_text(session.id, image), timeout=self._timeout_s
            )
        except TimeoutError as exc:
            raise BouncerError(f"timed out after {self._timeout_s}s") from exc
        except BouncerError:
            raise
        except Exception as exc:
            raise BouncerError(f"model call failed: {exc!r}") from exc
        finally:
            await sessions.delete_session(
                app_name=self._runner.app_name, user_id=self.USER_ID, session_id=session.id
            )

        try:
            return BouncerVerdict.model_validate_json(text)
        except ValidationError as exc:
            raise BouncerError("model output did not match BouncerVerdict") from exc

    async def _final_text(self, session_id: str, image: ImageInput) -> str:
        message = types.Content(
            role="user",
            parts=[types.Part.from_bytes(data=image.data, mime_type=image.mime_type)],
        )
        async for event in self._runner.run_async(
            user_id=self.USER_ID, session_id=session_id, new_message=message
        ):
            # ADK reports model/API failures (bad key, quota, safety block) as error events.
            if event.error_code or event.error_message:
                raise BouncerError(f"model error {event.error_code}: {event.error_message}")
            if event.is_final_response():
                parts = event.content.parts if event.content else None
                if not parts:
                    raise BouncerError("final response had no content")
                return "".join(part.text or "" for part in parts)
        raise BouncerError("agent finished without a final response")


def create_bouncer() -> AdkBouncer:
    """The production Bouncer: ADK Runner + in-memory sessions, Gemini via GOOGLE_API_KEY."""
    runner = Runner(
        agent=build_bouncer_agent(),
        app_name=APP_NAME,
        session_service=InMemorySessionService(),
    )
    return AdkBouncer(runner)
