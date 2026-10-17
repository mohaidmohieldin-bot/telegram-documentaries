"""In-memory session store keyed by chat_id."""

import pytest
from pydantic import ValidationError

from telegram_documentaries.session import Phase, Session, SessionStore


def test_new_chat_starts_awaiting_photo() -> None:
    session = SessionStore().get(1)
    assert session.chat_id == 1
    assert session.phase is Phase.AWAITING_PHOTO
    assert session.schema_version == 1


def test_set_phase_persists() -> None:
    store = SessionStore()
    returned = store.set_phase(1, Phase.PHOTO_ACCEPTED)
    assert returned.phase is Phase.PHOTO_ACCEPTED
    assert store.get(1).phase is Phase.PHOTO_ACCEPTED


def test_reset_returns_to_default() -> None:
    store = SessionStore()
    store.set_phase(1, Phase.PHOTO_ACCEPTED)
    store.reset(1)
    assert store.get(1) == Session(chat_id=1)


def test_reset_of_unknown_chat_is_harmless() -> None:
    store = SessionStore()
    store.reset(999)
    assert store.get(999).phase is Phase.AWAITING_PHOTO


def test_reset_is_idempotent() -> None:
    store = SessionStore()
    store.set_phase(1, Phase.PHOTO_ACCEPTED)
    store.reset(1)
    store.reset(1)
    assert store.get(1).phase is Phase.AWAITING_PHOTO


def test_chats_are_isolated() -> None:
    store = SessionStore()
    store.set_phase(1, Phase.PHOTO_ACCEPTED)
    assert store.get(2).phase is Phase.AWAITING_PHOTO
    store.reset(2)
    assert store.get(1).phase is Phase.PHOTO_ACCEPTED


def test_sessions_are_immutable() -> None:
    session = SessionStore().get(1)
    with pytest.raises(ValidationError):
        session.phase = Phase.PHOTO_ACCEPTED  # type: ignore[misc]


def test_chat_id_must_be_an_integer() -> None:
    # A str/int mismatch would silently split one user into two sessions.
    with pytest.raises(ValidationError):
        Session(chat_id="1")  # type: ignore[arg-type]
