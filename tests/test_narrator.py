"""The Narrator: script text -> Gemini TTS -> validated WAV voiceover (no network)."""

import asyncio
import base64
from types import SimpleNamespace
from typing import Any

import pytest

from telegram_documentaries.media import VoiceoverAudio
from telegram_documentaries.narrator import (
    NARRATOR_STYLE,
    NARRATOR_VOICE,
    TTS_MODEL,
    GeminiTts,
    Narrator,
    NarratorError,
    TtsRequest,
)
from telegram_documentaries.session import NarrationScript
from tests.audio_fakes import make_wav

SCRIPT = NarrationScript(text=" ".join(["Here, in the hush of dusk, the raccoon stirs."] * 7))
WAV = make_wav(20.0)


class FakeSynth:
    def __init__(self, result: bytes | Exception = WAV, delay_s: float = 0.0) -> None:
        self.result = result
        self.delay_s = delay_s
        self.requests: list[TtsRequest] = []

    async def __call__(self, request: TtsRequest) -> bytes:
        self.requests.append(request)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


# --- Narrator ----------------------------------------------------------------------------


def test_voice_settings() -> None:
    assert TTS_MODEL == "gemini-3.8-flash-tts"
    assert NARRATOR_VOICE == "Enceladus"
    assert "hushed" in NARRATOR_STYLE and "reverent" in NARRATOR_STYLE


async def test_narrates_the_script_with_the_narrator_voice() -> None:
    synth = FakeSynth()
    audio = await Narrator(synth, timeout_s=5.0).narrate(SCRIPT)

    assert audio == VoiceoverAudio(data=WAV)
    assert synth.requests == [
        TtsRequest(model=TTS_MODEL, voice=NARRATOR_VOICE, style=NARRATOR_STYLE, text=SCRIPT.text)
    ]


@pytest.mark.parametrize(
    "result",
    [b"not audio", make_wav(0.2), ConnectionError("down"), NarratorError("no audio returned")],
)
async def test_failures_raise_narrator_error(result: bytes | Exception) -> None:
    with pytest.raises(NarratorError):
        await Narrator(FakeSynth(result), timeout_s=5.0).narrate(SCRIPT)


async def test_timeout_raises_narrator_error() -> None:
    with pytest.raises(NarratorError, match="timed out"):
        await Narrator(FakeSynth(delay_s=1.0), timeout_s=0.05).narrate(SCRIPT)


# --- Gemini TTS adapter (fake client) ---------------------------------------------------------


class FakeInteractions:
    def __init__(self, output_audio: object) -> None:
        self.output_audio = output_audio
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        return SimpleNamespace(output_audio=self.output_audio)


def fake_client(output_audio: object) -> SimpleNamespace:
    return SimpleNamespace(interactions=FakeInteractions(output_audio))


REQUEST = TtsRequest(model=TTS_MODEL, voice="Enceladus", style="hushed", text="Here it is.")


async def test_adapter_builds_the_interactions_request_and_decodes_audio() -> None:
    client = fake_client(SimpleNamespace(data=base64.b64encode(WAV).decode()))
    assert await GeminiTts(client).synthesize(REQUEST) == WAV

    (call,) = client.interactions.calls
    assert call["model"] == TTS_MODEL
    (turn,) = call["input"]
    assert turn["type"] == "user_input"
    (part,) = turn["content"]
    assert part["text"] == "Here it is."
    assert part["annotations"] == [{"type": "speech_metadata", "style": "hushed"}]
    assert call["response_format"] == {"type": "audio", "mime_type": "audio/wav"}
    assert call["generation_config"] == {"speech_config": [{"voice": "Enceladus"}]}


async def test_adapter_accepts_raw_bytes_too() -> None:
    client = fake_client(SimpleNamespace(data=WAV))
    assert await GeminiTts(client).synthesize(REQUEST) == WAV


@pytest.mark.parametrize(
    "output_audio", [None, SimpleNamespace(data=None), SimpleNamespace(data="")]
)
async def test_adapter_without_audio_raises(output_audio: object) -> None:
    with pytest.raises(NarratorError, match="no audio"):
        await GeminiTts(fake_client(output_audio)).synthesize(REQUEST)
