"""Session state v5: phases and transitions through DONE, handoff, and the contracts."""

import pytest
from pydantic import ValidationError

from telegram_documentaries.media import ImageInput
from telegram_documentaries.session import (
    QA,
    Dossier,
    InterviewHandoff,
    InvalidTransition,
    NarrationScript,
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


TRANSCRIPT = (QA(question="What do you hoard?", answer="Mugs."),)
HANDOFF = InterviewHandoff(photo=PHOTO, dossier=DOSSIER, transcript=TRANSCRIPT)
SCRIPT = NarrationScript(text=" ".join(["Here, in the hush of dusk, the raccoon stirs."] * 7))


def interviewing(store: SessionStore, chat_id: int = 1) -> SessionStore:
    store.start_interview(chat_id, PHOTO, "What do you hoard?")
    return store


# --- Defaults and isolation --------------------------------------------------------


def test_new_chat_starts_awaiting_photo_with_empty_state() -> None:
    session = SessionStore().get(1)
    assert session == Session(chat_id=1)
    assert session.schema_version == 5
    assert session.script is None
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


# --- Portrait delivery -------------------------------------------------------------------


def completed(store: SessionStore, chat_id: int = 1) -> SessionStore:
    interviewing(store, chat_id)
    store.complete_interview(chat_id, "Mugs.", DOSSIER)
    return store


def test_deliver_portrait_after_completion() -> None:
    store = completed(SessionStore())
    session = store.deliver_portrait(1)
    assert session.phase is Phase.PORTRAIT_DELIVERED
    assert session.dossier == DOSSIER
    assert store.get(1) == session


@pytest.mark.parametrize("setup", ["fresh", "interviewing", "delivered"])
def test_deliver_portrait_from_wrong_phase_is_invalid(setup: str) -> None:
    store = SessionStore()
    if setup == "interviewing":
        interviewing(store)
    elif setup == "delivered":
        completed(store).deliver_portrait(1)
    with pytest.raises(InvalidTransition):
        store.deliver_portrait(1)


def test_new_interview_can_start_after_delivery() -> None:
    store = completed(SessionStore())
    store.deliver_portrait(1)
    session = store.start_interview(1, PHOTO, "Fresh?")
    assert session.phase is Phase.INTERVIEWING
    assert session.dossier is None


def test_handoff_still_available_after_delivery() -> None:
    store = completed(SessionStore())
    store.deliver_portrait(1)
    assert store.get(1).handoff() == HANDOFF


# --- Script --------------------------------------------------------------------------------


def delivered(store: SessionStore, chat_id: int = 1) -> SessionStore:
    completed(store, chat_id).deliver_portrait(chat_id)
    return store


def test_store_script_after_portrait() -> None:
    store = delivered(SessionStore())
    session = store.store_script(1, SCRIPT)
    assert session.phase is Phase.SCRIPT_READY
    assert session.script == SCRIPT
    assert store.get(1) == session


@pytest.mark.parametrize("setup", ["fresh", "interviewing", "completed", "scripted"])
def test_store_script_from_wrong_phase_is_invalid(setup: str) -> None:
    store = SessionStore()
    if setup == "interviewing":
        interviewing(store)
    elif setup == "completed":
        completed(store)
    elif setup == "scripted":
        delivered(store).store_script(1, SCRIPT)
    with pytest.raises(InvalidTransition):
        store.store_script(1, SCRIPT)


def test_new_interview_after_script_clears_it() -> None:
    store = delivered(SessionStore())
    store.store_script(1, SCRIPT)
    session = store.start_interview(1, PHOTO, "Fresh?")
    assert session.phase is Phase.INTERVIEWING
    assert session.script is None


def test_handoff_available_when_script_ready() -> None:
    store = delivered(SessionStore())
    store.store_script(1, SCRIPT)
    assert store.get(1).handoff().transcript == TRANSCRIPT


# --- Finish ------------------------------------------------------------------------------------


def scripted(store: SessionStore, chat_id: int = 1) -> SessionStore:
    delivered(store, chat_id).store_script(chat_id, SCRIPT)
    return store


def test_finish_after_script() -> None:
    store = scripted(SessionStore())
    session = store.finish(1)
    assert session.phase is Phase.DONE
    assert session.script == SCRIPT
    assert session.handoff() == HANDOFF


@pytest.mark.parametrize("setup", ["fresh", "completed", "delivered", "done"])
def test_finish_from_wrong_phase_is_invalid(setup: str) -> None:
    store = SessionStore()
    if setup == "completed":
        completed(store)
    elif setup == "delivered":
        delivered(store)
    elif setup == "done":
        scripted(store).finish(1)
    with pytest.raises(InvalidTransition):
        store.finish(1)


def test_new_interview_after_done() -> None:
    store = scripted(SessionStore())
    store.finish(1)
    session = store.start_interview(1, PHOTO, "Again?")
    assert session.phase is Phase.INTERVIEWING
    assert session.script is None


# --- NarrationScript contract ------------------------------------------------------------------


def words(n: int) -> str:
    return " ".join(["word"] * n)


@pytest.mark.parametrize("n", [60, 75, 90])
def test_script_accepts_60_to_90_words(n: int) -> None:
    assert NarrationScript(text=words(n)).word_count == n


@pytest.mark.parametrize("n", [0, 59, 91])
def test_script_rejects_out_of_range_word_counts(n: int) -> None:
    with pytest.raises(ValidationError, match=f"{n} words"):
        NarrationScript(text=words(n))


def test_script_rejects_multiple_paragraphs() -> None:
    with pytest.raises(ValidationError, match="one paragraph"):
        NarrationScript(text=words(40) + "\n\n" + words(40))


def test_script_collapses_whitespace() -> None:
    script = NarrationScript(text="  " + words(30) + "\n" + words(30) + "\t  ")
    assert script.text == words(60)


# --- Handoff -------------------------------------------------------------------------------


def test_handoff_carries_photo_and_dossier() -> None:
    store = interviewing(SessionStore())
    store.complete_interview(1, "Mugs.", DOSSIER)
    assert store.get(1).handoff() == HANDOFF


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
