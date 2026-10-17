"""Opt-in live check of the Scripter against the real Gemini API.

Run with `scripts/test-live` (needs GEMINI_API_KEY). Prints the narration so you can
read it; makes one or two small Gemini calls.
"""

import pytest

from telegram_documentaries.config import Settings, export_gemini_credentials
from telegram_documentaries.media import ImageInput
from telegram_documentaries.scripter import create_scripter
from telegram_documentaries.session import QA, Dossier, InterviewHandoff

pytestmark = pytest.mark.live

HANDOFF = InterviewHandoff(
    photo=ImageInput(data=b"\xff\xd8unused", mime_type="image/jpeg"),
    dossier=Dossier(
        profile="A stoic gamer who guards the sofa and fuels every raid with instant noodles.",
        quirks=("defends territory with Naruto hand signs", "silent during disputes"),
        suggested_animal="praying mantis",
        animal_rationale="Perfectly still for hours, then a sudden tactical strike.",
    ),
    transcript=(
        QA(question="What fuels your late-night quests?", answer="Indomie, always Indomie"),
        QA(question="How do you defend your territory?", answer="naruto hand signals"),
        QA(question="Dramatic flourish or brooding silence?", answer="silent"),
    ),
)


@pytest.fixture(scope="module", autouse=True)
def gemini_credentials() -> None:
    try:
        export_gemini_credentials(Settings())
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        pytest.skip(f"GEMINI_API_KEY / TELEGRAM_BOT_TOKEN not configured: {exc.__class__.__name__}")


async def test_writes_a_valid_narration() -> None:
    script = await create_scripter().write(HANDOFF)
    print(f"\n[{script.word_count} words] {script.text}")
    assert 60 <= script.word_count <= 90
    assert "mantis" in script.text.lower()
