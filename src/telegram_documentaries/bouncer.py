"""The Bouncer: a Google ADK vision agent that checks a photo contains a human.

Stateless: each check runs in a throwaway ADK session (see agents.py).
"""

from typing import ClassVar, Protocol

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from telegram_documentaries.agents import AgentCallError, run_structured_agent
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


class BouncerError(AgentCallError):
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
        return await run_structured_agent(
            self._runner,
            user_id=self.USER_ID,
            parts=[types.Part.from_bytes(data=image.data, mime_type=image.mime_type)],
            schema=BouncerVerdict,
            error=BouncerError,
            timeout_s=self._timeout_s,
        )


def create_bouncer() -> AdkBouncer:
    """The production Bouncer: ADK Runner + in-memory sessions, Gemini via GOOGLE_API_KEY."""
    runner = Runner(
        agent=build_bouncer_agent(),
        app_name=APP_NAME,
        session_service=InMemorySessionService(),
    )
    return AdkBouncer(runner)
