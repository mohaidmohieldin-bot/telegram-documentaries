"""The Narrator: turns the script into a spoken voiceover with Gemini TTS.

Not an agent (TECH.md): a plain class around one TTS call. Gemini's Interactions API
returns WAV audio as base64; the synchronous client call runs in a worker thread.
"""

import asyncio
import base64
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from google import genai
from pydantic import BaseModel, ConfigDict, ValidationError

from telegram_documentaries.logging_setup import logged_stage
from telegram_documentaries.media import VoiceoverAudio
from telegram_documentaries.session import NarrationScript

TTS_MODEL = "gemini-3.8-flash-tts"
NARRATOR_VOICE = "Enceladus"  # described by Google as "breathy"
NARRATOR_STYLE = (
    "hushed, reverent and unhurried, like a wildlife documentary narrator whispering "
    "so as not to disturb a rare creature; warm, with gentle pauses"
)
NARRATOR_TIMEOUT_S = 60.0


class NarratorError(Exception):
    """The Narrator could not produce a valid voiceover."""


class NarratorPort(Protocol):
    async def narrate(self, script: NarrationScript) -> VoiceoverAudio: ...


class TtsRequest(BaseModel):
    """The typed boundary between the Narrator and the TTS adapter."""

    model_config = ConfigDict(frozen=True)

    model: str
    voice: str
    style: str
    text: str


Synthesize = Callable[[TtsRequest], Awaitable[bytes]]


class GeminiTts:
    """Adapter for Gemini TTS via the Interactions API (returns WAV bytes)."""

    def __init__(self, client: Any) -> None:
        self._client = client

    async def synthesize(self, request: TtsRequest) -> bytes:
        interaction = await asyncio.to_thread(
            self._client.interactions.create,
            model=request.model,
            input=[
                {
                    "type": "user_input",
                    "content": [
                        {
                            "type": "text",
                            "text": request.text,
                            "annotations": [{"type": "speech_metadata", "style": request.style}],
                        },
                    ],
                },
            ],
            response_format={"type": "audio", "mime_type": "audio/wav"},
            generation_config={"speech_config": [{"voice": request.voice}]},
        )
        audio = getattr(interaction, "output_audio", None)
        data = getattr(audio, "data", None)
        if not data:
            raise NarratorError("TTS returned no audio")
        return base64.b64decode(data) if isinstance(data, str) else bytes(data)


class Narrator:
    def __init__(self, synthesize: Synthesize, timeout_s: float = NARRATOR_TIMEOUT_S) -> None:
        self._synthesize = synthesize
        self._timeout_s = timeout_s

    @logged_stage("narrator")
    async def narrate(self, script: NarrationScript) -> VoiceoverAudio:
        request = TtsRequest(
            model=TTS_MODEL, voice=NARRATOR_VOICE, style=NARRATOR_STYLE, text=script.text
        )
        try:
            data = await asyncio.wait_for(self._synthesize(request), timeout=self._timeout_s)
        except TimeoutError as exc:
            raise NarratorError(f"timed out after {self._timeout_s}s") from exc
        except NarratorError:
            raise
        except Exception as exc:
            raise NarratorError(f"TTS call failed: {exc!r}") from exc
        try:
            return VoiceoverAudio(data=data)
        except ValidationError as exc:
            raise NarratorError("TTS output was not a valid voiceover") from exc


def create_narrator() -> Narrator:
    """The production Narrator: Gemini TTS, authenticated via GOOGLE_API_KEY."""
    return Narrator(GeminiTts(genai.Client()).synthesize)
