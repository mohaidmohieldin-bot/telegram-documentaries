"""Typed settings loaded from the environment and `.env`."""

from typing import Any

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Construction fails with a ValidationError if invalid."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: SecretStr

    @field_validator("telegram_bot_token", mode="before")
    @classmethod
    def _check_token_shape(cls, value: Any) -> Any:
        """A bot token looks like '<numeric bot id>:<secret>' (as issued by @BotFather)."""
        if not isinstance(value, str):
            return value
        token = value.strip()
        bot_id, sep, secret = token.partition(":")
        if not (sep and bot_id.isdigit() and secret):
            raise ValueError(
                "TELEGRAM_BOT_TOKEN must look like '<bot id>:<secret>'; get one from @BotFather"
            )
        return token
