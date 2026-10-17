"""Opt-in live check of the Converter against the real Gemini API.

Run with `scripts/test-live`. Needs GEMINI_API_KEY and tests/live/fixtures/person.jpg.
The generated portrait is saved to tests/live/output/ (git-ignored) so you can look at it.
"""

from pathlib import Path

import pytest

from telegram_documentaries.config import Settings, export_gemini_credentials
from telegram_documentaries.converter import create_converter
from telegram_documentaries.media import ImageInput
from telegram_documentaries.session import Dossier, InterviewHandoff
from tests.live.test_bouncer_live import load_image

pytestmark = pytest.mark.live

OUTPUT = Path(__file__).parent / "output"
EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}

DOSSIER = Dossier(
    profile="A loud, joyful performer who serenades the whole neighbourhood.",
    quirks=("sings in group choruses", "never bows after a show"),
    suggested_animal="blue jay",
    animal_rationale="Highly social, famously loud and proud of it.",
)


@pytest.fixture(scope="module", autouse=True)
def gemini_credentials() -> None:
    try:
        export_gemini_credentials(Settings())
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        pytest.skip(f"GEMINI_API_KEY / TELEGRAM_BOT_TOKEN not configured: {exc.__class__.__name__}")


async def test_person_photo_becomes_a_hybrid_portrait() -> None:
    photo: ImageInput = load_image("person.jpg")
    portrait = await create_converter().convert(InterviewHandoff(photo=photo, dossier=DOSSIER))

    assert len(portrait.data) > 10_000  # a real image, not a stub
    OUTPUT.mkdir(exist_ok=True)
    path = OUTPUT / f"portrait.{EXTENSIONS[portrait.mime_type]}"
    path.write_bytes(portrait.data)
    print(f"\nSaved portrait to {path}")
