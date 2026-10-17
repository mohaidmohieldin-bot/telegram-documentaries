"""The Converter: photo + Dossier in, hybrid portrait out (fake runner, no network)."""

import json

import pytest
from google.genai import types

from telegram_documentaries.converter import (
    CONVERTER_MODEL,
    Converter,
    ConverterError,
    build_converter_agent,
)
from telegram_documentaries.media import ImageInput, PortraitImage
from telegram_documentaries.session import QA, Dossier, InterviewHandoff
from tests.adk_fakes import FakeEvent, FakeRunner

PHOTO = ImageInput(data=b"\xff\xd8selfie-bytes", mime_type="image/jpeg")
DOSSIER = Dossier(
    profile="A loud, joyful performer who serenades the whole street.",
    quirks=("sings in group choruses", "never bows after a show"),
    suggested_animal="blue jay",
    animal_rationale="Highly social and famously loud.",
)
TRANSCRIPT = (QA(question="What do you sing?", answer="Loud choruses."),)
HANDOFF = InterviewHandoff(photo=PHOTO, dossier=DOSSIER, transcript=TRANSCRIPT)
PNG = b"\x89PNG\r\n\x1a\nhybrid"


def portrait_event() -> FakeEvent:
    return FakeEvent(None, parts=[types.Part.from_bytes(data=PNG, mime_type="image/png")])


def converter(runner: FakeRunner) -> Converter:
    return Converter(runner.as_runner(), timeout_s=5.0)


def test_agent_uses_flash_image_with_image_output() -> None:
    agent = build_converter_agent()
    assert CONVERTER_MODEL == "gemini-3.1-flash-image"
    assert agent.model == CONVERTER_MODEL
    assert agent.generate_content_config is not None
    modalities = agent.generate_content_config.response_modalities or []
    assert {str(m).upper().split(".")[-1] for m in modalities} == {"TEXT", "IMAGE"}


def test_instruction_covers_likeness_habitat_and_no_text() -> None:
    instruction = str(build_converter_agent().instruction).lower()
    phrases = (
        "photorealistic",
        "recognisable",
        "habitat",
        "no text",
        "exactly one",
        "ignore any instructions",
    )
    for phrase in phrases:
        assert phrase in instruction


async def test_sends_photo_and_dossier_as_quoted_data() -> None:
    runner = FakeRunner([portrait_event()])
    await converter(runner).convert(HANDOFF)

    (message,) = runner.messages
    parts = message.parts or []
    blobs = [p.inline_data for p in parts if p.inline_data]
    assert len(blobs) == 1
    assert (blobs[0].data, blobs[0].mime_type) == (PHOTO.data, "image/jpeg")

    text = runner.sent_text()
    assert json.dumps("blue jay") in text
    assert json.dumps("sings in group choruses") in text


async def test_returns_the_generated_portrait() -> None:
    portrait = await converter(FakeRunner([portrait_event()])).convert(HANDOFF)
    assert portrait == PortraitImage(data=PNG, mime_type="image/png")


@pytest.mark.parametrize(
    "response",
    [
        [FakeEvent("Sorry, I can't create that image.")],
        [FakeEvent(None, error_code="SAFETY", error_message="blocked")],
        ConnectionError("down"),
    ],
)
async def test_failures_raise_converter_error(response: list[FakeEvent] | Exception) -> None:
    with pytest.raises(ConverterError):
        await converter(FakeRunner(response)).convert(HANDOFF)


async def test_timeout_raises_converter_error() -> None:
    runner = FakeRunner([portrait_event()], delay_s=1.0)
    with pytest.raises(ConverterError, match="timed out"):
        await Converter(runner.as_runner(), timeout_s=0.05).convert(HANDOFF)
