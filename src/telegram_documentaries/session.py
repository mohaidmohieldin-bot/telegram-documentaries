"""In-memory session state, keyed by Telegram chat_id.

`SessionStore` is the single driver for session state: nothing else mutates it, and
each transition checks the phase it starts from (a wrong-phase call is a bug and
raises `InvalidTransition`).
"""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from telegram_documentaries.media import ImageInput

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
Answer = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

MAX_ANSWER_CHARS = 1000


class Phase(StrEnum):
    AWAITING_PHOTO = "awaiting_photo"
    INTERVIEWING = "interviewing"
    INTERVIEW_COMPLETE = "interview_complete"


class InvalidTransition(Exception):
    """A session transition was attempted from the wrong phase (a programming error)."""


class QA(BaseModel):
    model_config = ConfigDict(frozen=True)

    question: Question
    answer: Answer


class Dossier(BaseModel):
    """The Interviewer's behavioural profile, handed to the next pipeline stage."""

    model_config = ConfigDict(frozen=True)

    profile: str = Field(
        min_length=1,
        max_length=800,
        description="A concise behavioural/personality profile in 2-4 sentences.",
    )
    quirks: tuple[Annotated[str, StringConstraints(min_length=1, max_length=150)], ...] = Field(
        min_length=2, max_length=5, description="2-5 short, specific quirks or habits."
    )
    suggested_animal: str = Field(
        min_length=1, max_length=40, description="One animal species, e.g. 'honey badger'."
    )
    animal_rationale: str = Field(
        min_length=1, max_length=300, description="One sentence on why this animal fits."
    )


class InterviewHandoff(BaseModel):
    """What the next stage (the Converter) receives once the interview is complete."""

    model_config = ConfigDict(frozen=True)

    photo: ImageInput
    dossier: Dossier


class Session(BaseModel):
    """One user's conversation state. Immutable: changes go through SessionStore."""

    model_config = ConfigDict(frozen=True, strict=True)

    schema_version: Literal[2] = 2
    chat_id: int
    phase: Phase = Phase.AWAITING_PHOTO
    photo: ImageInput | None = None
    transcript: tuple[QA, ...] = ()
    pending_question: str | None = None
    dossier: Dossier | None = None

    def handoff(self) -> InterviewHandoff:
        if self.phase is not Phase.INTERVIEW_COMPLETE or not self.photo or not self.dossier:
            raise InvalidTransition(f"chat {self.chat_id}: no completed interview to hand off")
        return InterviewHandoff(photo=self.photo, dossier=self.dossier)


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, Session] = {}

    def get(self, chat_id: int) -> Session:
        """Return the chat's session, or a fresh default one."""
        return self._sessions.get(chat_id) or Session(chat_id=chat_id)

    def reset(self, chat_id: int) -> None:
        """Forget everything about this chat; the next get() returns the default."""
        self._sessions.pop(chat_id, None)

    def start_interview(self, chat_id: int, photo: ImageInput, first_question: str) -> Session:
        current = self.get(chat_id)
        self._require(current, Phase.AWAITING_PHOTO, Phase.INTERVIEW_COMPLETE)
        return self._save(
            Session(
                chat_id=chat_id,
                phase=Phase.INTERVIEWING,
                photo=photo,
                pending_question=first_question,
            )
        )

    def record_answer(self, chat_id: int, answer: str, next_question: str) -> Session:
        current = self.get(chat_id)
        transcript = self._answered(current, answer)
        return self._save(
            current.model_copy(update={"transcript": transcript, "pending_question": next_question})
        )

    def complete_interview(self, chat_id: int, answer: str, dossier: Dossier) -> Session:
        current = self.get(chat_id)
        transcript = self._answered(current, answer)
        return self._save(
            current.model_copy(
                update={
                    "phase": Phase.INTERVIEW_COMPLETE,
                    "transcript": transcript,
                    "pending_question": None,
                    "dossier": dossier,
                }
            )
        )

    def _answered(self, current: Session, answer: str) -> tuple[QA, ...]:
        self._require(current, Phase.INTERVIEWING)
        if current.pending_question is None:
            raise InvalidTransition(f"chat {current.chat_id}: no question is pending")
        return (*current.transcript, QA(question=current.pending_question, answer=answer))

    @staticmethod
    def _require(session: Session, *allowed: Phase) -> None:
        if session.phase not in allowed:
            raise InvalidTransition(
                f"chat {session.chat_id}: cannot do this in phase {session.phase.value}"
            )

    def _save(self, session: Session) -> Session:
        self._sessions[session.chat_id] = session
        return session
