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


@dataclass(frozen=True)
class Config:
    slack_bot_token: str
    google_credentials_file: str
    spreadsheet_id: str
    worksheet_name: str
    # Opaque Slack custom-profile field id holding the "section" string (e.g. "Xf0123ABC").
    section_field_id: str
    poll_interval_seconds: int

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            slack_bot_token=_require("SLACK_BOT_TOKEN"),
            google_credentials_file=_require("GOOGLE_CREDENTIALS_FILE"),
            spreadsheet_id=_require("SPREADSHEET_ID"),
            worksheet_name=os.environ.get("WORKSHEET_NAME", "Members"),
            section_field_id=_require("SECTION_FIELD_ID"),
            poll_interval_seconds=int(os.environ.get("POLL_INTERVAL_SECONDS", "300")),
        )
