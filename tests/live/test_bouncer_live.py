"""Opt-in live checks of the Bouncer against the real Gemini API.

Run with `scripts/test-live`. Needs GEMINI_API_KEY (in .env or the environment) and
two images you supply in tests/live/fixtures/ (git-ignored, never committed):

    person.jpg     a photo with a clearly visible person
    landscape.jpg  a landscape or object with no people

(JPEG, PNG or WebP all work; the real type is detected from the file contents.)
"""

from pathlib import Path

import pytest

from telegram_documentaries.bouncer import create_bouncer
from telegram_documentaries.config import Settings, export_gemini_credentials
from telegram_documentaries.media import ImageInput

pytestmark = pytest.mark.live

FIXTURES = Path(__file__).parent / "fixtures"


def sniff_mime_type(data: bytes) -> str:
    """Detect the real image type from its first bytes (file extensions can lie)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    pytest.fail("fixture images must be JPEG, PNG or WebP")


def load_image(name: str) -> ImageInput:
    path = FIXTURES / name
    if not path.is_file():
        pytest.skip(f"add {path} to run this live test")
    data = path.read_bytes()
    return ImageInput.model_validate({"data": data, "mime_type": sniff_mime_type(data)})


@pytest.fixture(scope="module", autouse=True)
def gemini_credentials() -> None:
    try:
        export_gemini_credentials(Settings())
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        pytest.skip(f"GEMINI_API_KEY / TELEGRAM_BOT_TOKEN not configured: {exc.__class__.__name__}")


async def test_person_photo_is_classified_as_human() -> None:
    verdict = await create_bouncer().check(load_image("person.jpg"))
    assert verdict.human_present is True, verdict.reason


async def test_landscape_photo_is_classified_as_no_human() -> None:
    verdict = await create_bouncer().check(load_image("landscape.jpg"))
    assert verdict.human_present is False, verdict.reason
