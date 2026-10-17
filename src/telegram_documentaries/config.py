"""Typed settings loaded from the environment and `.env`."""

import os
from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _strip_and_reject_placeholder(value: Any) -> Any:
    """Strip whitespace; reject empty values and `.env.example` placeholders."""
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty")
    if stripped.startswith("your_") and stripped.endswith("_here"):
        raise ValueError("still the .env.example placeholder; put your real value in .env")
    return stripped


class Settings(BaseSettings):
    """Runtime configuration. Construction fails with a ValidationError if invalid."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: SecretStr
    gemini_api_key: SecretStr

    @field_validator("telegram_bot_token", mode="before")
    @classmethod
    def _check_token_shape(cls, value: Any) -> Any:
        """A bot token looks like '<numeric bot id>:<secret>' (as issued by @BotFather)."""
        token = _strip_and_reject_placeholder(value)
        if not isinstance(token, str):
            return token
        bot_id, sep, secret = token.partition(":")
        if not (sep and bot_id.isdigit() and secret):
            raise ValueError(
                "TELEGRAM_BOT_TOKEN must look like '<bot id>:<secret>'; get one from @BotFather"
            )
        return token

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _check_gemini_key(cls, value: Any) -> Any:
        return _strip_and_reject_placeholder(value)


def export_gemini_credentials(settings: Settings) -> None:
    """Expose the Gemini key where the ADK / google-genai client looks for it."""
    os.environ["GOOGLE_API_KEY"] = settings.gemini_api_key.get_secret_value()
