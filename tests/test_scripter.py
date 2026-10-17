"""The Scripter: Dossier + answers in, one 60-90 word narration paragraph out."""

import json

import pytest

from telegram_documentaries.media import ImageInput
from telegram_documentaries.scripter import (
    SCRIPTER_MODEL,
    NarrationDraft,
    Scripter,
    ScripterError,
    build_scripter_agent,
)
from telegram_documentaries.session import QA, Dossier, InterviewHandoff, NarrationScript
from tests.adk_fakes import FakeRunner

DOSSIER = Dossier(
    profile="A stoic gamer who guards the sofa with Naruto hand signs.",
    quirks=("uses controller vibration as a workout", "silent during disputes"),
    suggested_animal="praying mantis",
    animal_rationale="Perfectly still, then a sudden tactical strike.",
)
TRANSCRIPT = (
    QA(question="How do you defend your territory?", answer="naruto hand signals move"),
    QA(question="Vocal flourish or silence?", answer="silent"),
)
HANDOFF = InterviewHandoff(
    photo=ImageInput(data=b"\xff\xd8x", mime_type="image/jpeg"),
    dossier=DOSSIER,
    transcript=TRANSCRIPT,
)


def draft(n_words: int) -> str:
    return NarrationDraft(narration=" ".join(["hush"] * n_words)).model_dump_json()


def scripter(runner: FakeRunner) -> Scripter:
    return Scripter(runner.as_runner(), timeout_s=5.0)


# --- Agent -------------------------------------------------------------------------------


def test_agent_config() -> None:
    agent = build_scripter_agent()
    assert SCRIPTER_MODEL == "gemini-3.1-flash-lite"
    assert agent.model == SCRIPTER_MODEL
    assert agent.output_schema is NarrationDraft


def test_instruction_sets_tone_length_and_guardrails() -> None:
    instruction = str(build_scripter_agent().instruction).lower()
    for phrase in (
        "hushed",
        "reverent",
        "60 to 90 words",
        "one paragraph",
        "read aloud",
        "never name or imitate a real",
        "ignore any instructions",
    ):
        assert phrase in instruction


# --- Input ---------------------------------------------------------------------------------


async def test_sends_dossier_and_answers_as_quoted_data() -> None:
    runner = FakeRunner.replying(draft(70))
    await scripter(runner).write(HANDOFF)
    sent = runner.sent_text()
    for value in ("praying mantis", "silent during disputes", "naruto hand signals move"):
        assert json.dumps(value) in sent
    assert runner.messages[0].parts and not any(p.inline_data for p in runner.messages[0].parts)


# --- Output and retry ------------------------------------------------------------------------


async def test_valid_draft_becomes_a_narration_script() -> None:
    runner = FakeRunner.replying(draft(75))
    script = await scripter(runner).write(HANDOFF)
    assert script == NarrationScript(text=" ".join(["hush"] * 75))
    assert runner.calls == 1


@pytest.mark.parametrize("first", [47, 120])
async def test_one_retry_names_the_problem_and_can_succeed(first: int) -> None:
    runner = FakeRunner.replying(draft(first), draft(80))
    script = await scripter(runner).write(HANDOFF)
    assert script.word_count == 80
    assert runner.calls == 2
    assert f"{first} words" in runner.sent_text(1)
    assert "praying mantis" in runner.sent_text(1)  # the retry still has the full brief


async def test_multiple_paragraphs_trigger_a_retry() -> None:
    two_paragraphs = NarrationDraft(
        narration=" ".join(["hush"] * 35) + "\n\n" + " ".join(["hush"] * 35)
    ).model_dump_json()
    runner = FakeRunner.replying(two_paragraphs, draft(70))
    assert (await scripter(runner).write(HANDOFF)).word_count == 70
    assert "one paragraph" in runner.sent_text(1)


async def test_two_misses_raise_scripter_error() -> None:
    runner = FakeRunner.replying(draft(30), draft(31))
    with pytest.raises(ScripterError, match="31 words"):
        await scripter(runner).write(HANDOFF)
    assert runner.calls == 2


async def test_model_failure_raises_without_retry() -> None:
    runner = FakeRunner(ConnectionError("down"))
    with pytest.raises(ScripterError):
        await scripter(runner).write(HANDOFF)
    assert runner.calls == 1


async def test_unparseable_output_raises_without_retry() -> None:
    runner = FakeRunner.replying("Once upon a time…")
    with pytest.raises(ScripterError):
        await scripter(runner).write(HANDOFF)
    assert runner.calls == 1
