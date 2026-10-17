"""Settings are loaded from the environment and fail clearly when invalid."""

import os

import pytest
from pydantic import ValidationError

from telegram_documentaries.config import Settings, export_gemini_credentials

VALID_TOKEN = "123456789:AAH-example_token-value"
VALID_GEMINI_KEY = "AIzaSy-example-gemini-key"


def load(
    monkeypatch: pytest.MonkeyPatch,
    token: str | None = VALID_TOKEN,
    gemini_key: str | None = VALID_GEMINI_KEY,
) -> Settings:
    for name, value in (("TELEGRAM_BOT_TOKEN", token), ("GEMINI_API_KEY", gemini_key)):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    # _env_file=None keeps a developer's real .env out of the tests.
    return Settings(_env_file=None)


# --- Telegram token -----------------------------------------------------------


def test_loads_token_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch)
    assert settings.telegram_bot_token.get_secret_value() == VALID_TOKEN


def test_missing_token_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="telegram_bot_token"):
        load(monkeypatch, token=None)


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
        load(monkeypatch, token=bad_token)


def test_surrounding_whitespace_is_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, token=f"  {VALID_TOKEN}\n")
    assert settings.telegram_bot_token.get_secret_value() == VALID_TOKEN


# --- Gemini key ---------------------------------------------------------------


def test_loads_gemini_key_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch, gemini_key=f" {VALID_GEMINI_KEY} ")
    assert settings.gemini_api_key.get_secret_value() == VALID_GEMINI_KEY


def test_missing_gemini_key_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="gemini_api_key"):
        load(monkeypatch, gemini_key=None)


@pytest.mark.parametrize("bad_key", ["", "   ", "your_gemini_api_key_here"])
def test_empty_or_placeholder_gemini_key_fails(
    monkeypatch: pytest.MonkeyPatch, bad_key: str
) -> None:
    with pytest.raises(ValidationError, match="gemini_api_key"):
        load(monkeypatch, gemini_key=bad_key)


def test_secrets_are_hidden_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = load(monkeypatch)
    for secret in (VALID_TOKEN, VALID_GEMINI_KEY):
        assert secret not in repr(settings)
        assert secret not in str(settings)


def test_export_gemini_credentials_sets_google_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    # setenv first so monkeypatch restores the original value after the test.
    monkeypatch.setenv("GOOGLE_API_KEY", "stale-value")
    export_gemini_credentials(load(monkeypatch))
    assert os.environ["GOOGLE_API_KEY"] == VALID_GEMINI_KEY
