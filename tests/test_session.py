"""Session state v2: phases, interview transitions, handoff, and the data contracts."""

import pytest
from pydantic import ValidationError

from telegram_documentaries.media import ImageInput
from telegram_documentaries.session import (
    QA,
    Dossier,
    InterviewHandoff,
    InvalidTransition,
    Phase,
    Session,
    SessionStore,
)

PHOTO = ImageInput(data=b"\xff\xd8selfie", mime_type="image/jpeg")
DOSSIER = Dossier(
    profile="A nocturnal snack strategist who alphabetises spices.",
    quirks=("hums while thinking", "collects mugs"),
    suggested_animal="raccoon",
    animal_rationale="Night-time foraging and a love of shiny things.",
)


def interviewing(store: SessionStore, chat_id: int = 1) -> SessionStore:
    store.start_interview(chat_id, PHOTO, "What do you hoard?")
    return store


# --- Defaults and isolation --------------------------------------------------------


def test_new_chat_starts_awaiting_photo_with_empty_state() -> None:
    session = SessionStore().get(1)
    assert session == Session(chat_id=1)
    assert session.schema_version == 2
    assert session.phase is Phase.AWAITING_PHOTO
    assert session.photo is None
    assert session.transcript == ()
    assert session.pending_question is None
    assert session.dossier is None


def test_chats_are_isolated() -> None:
    store = interviewing(SessionStore(), chat_id=1)
    assert store.get(2).phase is Phase.AWAITING_PHOTO
    store.reset(2)
    assert store.get(1).phase is Phase.INTERVIEWING


def test_sessions_are_immutable() -> None:
    session = SessionStore().get(1)
    with pytest.raises(ValidationError):
        session.phase = Phase.INTERVIEWING  # type: ignore[misc]


def test_chat_id_must_be_an_integer() -> None:
    with pytest.raises(ValidationError):
        Session(chat_id="1")  # type: ignore[arg-type]


# --- Transitions ---------------------------------------------------------------------


def test_start_interview_stores_photo_and_first_question() -> None:
    session = SessionStore().start_interview(1, PHOTO, "What do you hoard?")
    assert session.phase is Phase.INTERVIEWING
    assert session.photo == PHOTO
    assert session.pending_question == "What do you hoard?"
    assert session.transcript == ()


def test_start_interview_after_completion_starts_fresh() -> None:
    store = interviewing(SessionStore())
    store.complete_interview(1, "Mugs.", DOSSIER)
    session = store.start_interview(1, PHOTO, "New question?")
    assert session.transcript == ()
    assert session.dossier is None


def test_start_interview_while_interviewing_is_invalid() -> None:
    store = interviewing(SessionStore())
    with pytest.raises(InvalidTransition):
        store.start_interview(1, PHOTO, "Again?")


def test_record_answer_appends_and_sets_next_question() -> None:
    store = interviewing(SessionStore())
    session = store.record_answer(1, "  Spoons.  ", "And why spoons?")
    assert session.transcript == (QA(question="What do you hoard?", answer="Spoons."),)
    assert session.pending_question == "And why spoons?"
    assert store.get(1) == session


def test_answers_accumulate_in_order() -> None:
    store = interviewing(SessionStore())
    store.record_answer(1, "Spoons.", "Why?")
    session = store.record_answer(1, "They're shiny.", "Favourite spoon?")
    assert [qa.answer for qa in session.transcript] == ["Spoons.", "They're shiny."]


def test_record_answer_outside_interview_is_invalid() -> None:
    with pytest.raises(InvalidTransition):
        SessionStore().record_answer(1, "hello", "next?")


def test_complete_interview_stores_final_answer_and_dossier() -> None:
    store = interviewing(SessionStore())
    session = store.complete_interview(1, "Mugs.", DOSSIER)
    assert session.phase is Phase.INTERVIEW_COMPLETE
    assert session.transcript[-1] == QA(question="What do you hoard?", answer="Mugs.")
    assert session.pending_question is None
    assert session.dossier == DOSSIER
    assert session.photo == PHOTO


def test_complete_interview_outside_interview_is_invalid() -> None:
    with pytest.raises(InvalidTransition):
        SessionStore().complete_interview(1, "Mugs.", DOSSIER)


def test_reset_clears_everything() -> None:
    store = interviewing(SessionStore())
    store.record_answer(1, "Spoons.", "Why?")
    store.reset(1)
    assert store.get(1) == Session(chat_id=1)


def test_reset_is_idempotent_and_harmless_for_unknown_chats() -> None:
    store = SessionStore()
    store.reset(999)
    store.reset(999)
    assert store.get(999).phase is Phase.AWAITING_PHOTO


# --- Handoff -------------------------------------------------------------------------------


def test_handoff_carries_photo_and_dossier() -> None:
    store = interviewing(SessionStore())
    store.complete_interview(1, "Mugs.", DOSSIER)
    assert store.get(1).handoff() == InterviewHandoff(photo=PHOTO, dossier=DOSSIER)


@pytest.mark.parametrize("started", [False, True])
def test_handoff_before_completion_is_invalid(started: bool) -> None:
    store = interviewing(SessionStore()) if started else SessionStore()
    with pytest.raises(InvalidTransition):
        store.get(1).handoff()


# --- Contracts -------------------------------------------------------------------------------


@pytest.mark.parametrize("answer", ["", "   ", "x" * 1001])
def test_qa_rejects_empty_or_overlong_answers(answer: str) -> None:
    with pytest.raises(ValidationError):
        QA(question="Q?", answer=answer)


def test_qa_accepts_answer_at_limit() -> None:
    assert len(QA(question="Q?", answer="x" * 1000).answer) == 1000


@pytest.mark.parametrize(
    "changes",
    [
        {"quirks": ("only one",)},
        {"quirks": tuple(f"quirk {i}" for i in range(6))},
        {"suggested_animal": ""},
        {"suggested_animal": "x" * 41},
        {"profile": "x" * 801},
        {"animal_rationale": ""},
    ],
)
def test_dossier_bounds(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Dossier.model_validate(DOSSIER.model_dump() | changes)
