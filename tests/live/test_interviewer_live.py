"""Opt-in live check of the Interviewer against the real Gemini API.

Run with `scripts/test-live` (needs GEMINI_API_KEY). Plays a full interview with
scripted answers; makes up to 8 small Gemini calls.
"""

import pytest

from telegram_documentaries.config import Settings, export_gemini_credentials
from telegram_documentaries.interviewer import (
    MAX_QUESTIONS,
    MIN_QUESTIONS,
    NextQuestion,
    create_interviewer,
)
from telegram_documentaries.session import QA, Dossier

pytestmark = pytest.mark.live

SCRIPTED_ANSWERS = [
    "I eat cereal at midnight, standing up, straight from the box.",
    "I alphabetise my spice rack and get twitchy if anyone moves the paprika.",
    "Under pressure I go very quiet and then reorganise a drawer.",
    "My secret talent is identifying any dog breed from across a park.",
    "I hum the same three notes whenever I'm concentrating.",
    "On weekends I nap in sunbeams like it's a competitive sport.",
    "I hoard tote bags; I currently own forty-two.",
]


@pytest.fixture(scope="module", autouse=True)
def gemini_credentials() -> None:
    try:
        export_gemini_credentials(Settings())
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        pytest.skip(f"GEMINI_API_KEY / TELEGRAM_BOT_TOKEN not configured: {exc.__class__.__name__}")


async def test_full_interview_produces_a_dossier_within_bounds() -> None:
    interviewer = create_interviewer()
    question = await interviewer.first_question()
    transcript: tuple[QA, ...] = ()
    dossier: Dossier | None = None

    for answer in SCRIPTED_ANSWERS:
        transcript = (*transcript, QA(question=question, answer=answer))
        step = await interviewer.next_step(transcript)
        if isinstance(step, Dossier):
            dossier = step
            break
        assert isinstance(step, NextQuestion)
        question = step.question

    assert dossier is not None, "interview did not finish within the scripted answers"
    assert MIN_QUESTIONS <= len(transcript) <= MAX_QUESTIONS
    assert dossier.suggested_animal.strip()
    assert len(dossier.quirks) >= 2
