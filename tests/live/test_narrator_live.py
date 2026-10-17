"""Opt-in live check of the Narrator against the real Gemini TTS API.

Run with `scripts/test-live` (needs GEMINI_API_KEY). Saves the voiceover to
tests/live/output/voiceover.wav (git-ignored) so you can listen to it.
"""

from pathlib import Path

import pytest

from telegram_documentaries.config import Settings, export_gemini_credentials
from telegram_documentaries.narrator import create_narrator
from telegram_documentaries.session import NarrationScript

pytestmark = pytest.mark.live

OUTPUT = Path(__file__).parent / "output"

SCRIPT = NarrationScript(
    text=(
        "Observe the gamer in his natural habitat, the couch. With the stillness of a "
        "praying mantis, he remains motionless for hours, conserving energy for the "
        "inevitable digital skirmish. He fuels this focused vigilance with a steaming bowl "
        "of Indomie, a ritualistic sustenance. Should an intruder approach his territory, "
        "he deploys intricate Naruto hand signs, a silent yet formidable warning. He does "
        "not speak, for the hunt requires absolute stillness."
    )
)


@pytest.fixture(scope="module", autouse=True)
def gemini_credentials() -> None:
    try:
        export_gemini_credentials(Settings())
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        pytest.skip(f"GEMINI_API_KEY / TELEGRAM_BOT_TOKEN not configured: {exc.__class__.__name__}")


async def test_script_becomes_a_voiceover() -> None:
    audio = await create_narrator().narrate(SCRIPT)

    assert 10 <= audio.duration_s <= 90
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / "voiceover.wav"
    path.write_bytes(audio.data)
    print(f"\nSaved {audio.duration_s:.1f}s voiceover to {path}")
