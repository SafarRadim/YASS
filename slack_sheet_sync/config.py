"""Configuration loaded from environment variables (.env supported)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


class ConfigError(RuntimeError):
    """Raised when a required environment variable is missing."""


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


AUTH_MODES = ("service_account", "oauth")


@dataclass(frozen=True)
class Config:
    slack_bot_token: str
    spreadsheet_id: str
    worksheet_name: str
    # Opaque Slack custom-profile field id holding the "section" string (e.g. "Xf0123ABC").
    section_field_id: str
    poll_interval_seconds: int
    # "service_account" (default) or "oauth".
    auth_mode: str
    # Used when auth_mode == "service_account".
    google_credentials_file: str
    # Used when auth_mode == "oauth".
    google_oauth_client_file: str
    google_oauth_token_file: str

    @classmethod
    def from_env(cls) -> Config:
        auth_mode = os.environ.get("GOOGLE_AUTH_MODE", "service_account").strip().lower()
        if auth_mode not in AUTH_MODES:
            raise ConfigError(f"GOOGLE_AUTH_MODE must be one of {AUTH_MODES}, got {auth_mode!r}")

        google_credentials_file = os.environ.get("GOOGLE_CREDENTIALS_FILE", "")
        google_oauth_client_file = os.environ.get("GOOGLE_OAUTH_CLIENT_FILE", "")
        google_oauth_token_file = os.environ.get("GOOGLE_OAUTH_TOKEN_FILE", "")

        if auth_mode == "service_account" and not google_credentials_file:
            raise ConfigError(
                "GOOGLE_CREDENTIALS_FILE is required when GOOGLE_AUTH_MODE=service_account"
            )
        if auth_mode == "oauth":
            if not google_oauth_client_file:
                raise ConfigError(
                    "GOOGLE_OAUTH_CLIENT_FILE is required when GOOGLE_AUTH_MODE=oauth"
                )
            if not google_oauth_token_file:
                raise ConfigError("GOOGLE_OAUTH_TOKEN_FILE is required when GOOGLE_AUTH_MODE=oauth")

        return cls(
            slack_bot_token=_require("SLACK_BOT_TOKEN"),
            spreadsheet_id=_require("SPREADSHEET_ID"),
            worksheet_name=os.environ.get("WORKSHEET_NAME", "Members"),
            section_field_id=_require("SECTION_FIELD_ID"),
            poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "300")),
            auth_mode=auth_mode,
            google_credentials_file=google_credentials_file,
            google_oauth_client_file=google_oauth_client_file,
            google_oauth_token_file=google_oauth_token_file,
        )
