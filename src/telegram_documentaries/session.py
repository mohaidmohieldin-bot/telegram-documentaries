"""In-memory session state, keyed by Telegram chat_id.

`SessionStore` is the single driver for session state: nothing else mutates it.
"""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict


class Phase(StrEnum):
    AWAITING_PHOTO = "awaiting_photo"
    PHOTO_ACCEPTED = "photo_accepted"


class Session(BaseModel):
    """One user's conversation state. Immutable: changes go through SessionStore."""

    model_config = ConfigDict(frozen=True, strict=True)

    schema_version: Literal[1] = 1
    chat_id: int
    phase: Phase = Phase.AWAITING_PHOTO


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, Session] = {}

    def get(self, chat_id: int) -> Session:
        """Return the chat's session, or a fresh default one."""
        return self._sessions.get(chat_id) or Session(chat_id=chat_id)

    def set_phase(self, chat_id: int, phase: Phase) -> Session:
        session = self.get(chat_id).model_copy(update={"phase": phase})
        self._sessions[chat_id] = session
        return session

    def reset(self, chat_id: int) -> None:
        """Forget everything about this chat; the next get() returns the default."""
        self._sessions.pop(chat_id, None)
