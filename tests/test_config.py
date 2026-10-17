"""Settings are loaded from the environment and fail clearly when invalid."""

import pytest
from pydantic import ValidationError

from telegram_documentaries.config import Settings

VALID_TOKEN = "123456789:AAH-example_token-value"


def load(monkeypatch: pytest.MonkeyPatch, token: str | None) -> Settings:
    if token is None:
        monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    else:
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", token)
    # _env_file=None keeps a developer's real .env out of the tests.
    return Settings(_env_file=None)


def test_loads_token_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, VALID_TOKEN)
    assert settings.telegram_bot_token.get_secret_value() == VALID_TOKEN


def test_token_is_hidden_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, VALID_TOKEN)
    assert VALID_TOKEN not in repr(settings)
    assert VALID_TOKEN not in str(settings)


def test_missing_token_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="telegram_bot_token"):
        load(monkeypatch, None)


@pytest.mark.parametrize(
    "bad_token",
    [
        "",
        "   ",
        "your_telegram_bot_token_here",  # placeholder from .env.example
        "123456789",  # missing the secret half
        ":AAH-secret",  # missing the bot id
        "abc:AAH-secret",  # non-numeric bot id
    ],
)
def test_malformed_token_fails(monkeypatch: pytest.MonkeyPatch, bad_token: str) -> None:
    with pytest.raises(ValidationError):
        load(monkeypatch, bad_token)


def test_surrounding_whitespace_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, f"  {VALID_TOKEN}\n")
    assert settings.telegram_bot_token.get_secret_value() == VALID_TOKEN
