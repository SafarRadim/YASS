"""Build an authorized gspread client from either a service account or user OAuth.

Two modes, selected by GOOGLE_AUTH_MODE:

- ``service_account`` (default): a service-account JSON key. The account is an external
  identity, so the target sheet must be shared with its email. Blocked if the org forbids
  external sharing.
- ``oauth``: act as a real user via a stored authorized-user token. The app inherits
  whatever access that user already has (e.g. via a Google Group / shared folder), which
  sidesteps external-sharing restrictions. Bootstrap the token once with
  ``python -m slack_sheet_sync.google_oauth_setup``.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import gspread
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials

if TYPE_CHECKING:
    from .config import Config

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def build_client(config: Config) -> gspread.Client:
    """Return an authorized gspread client for the configured auth mode."""
    if config.auth_mode == "oauth":
        creds = _load_oauth_credentials(config.google_oauth_token_file)
    else:
        creds = ServiceAccountCredentials.from_service_account_file(
            config.google_credentials_file, scopes=SCOPES
        )
    return gspread.authorize(creds)


def _load_oauth_credentials(token_file: str) -> UserCredentials:
    """Load a stored authorized-user token, refreshing (and re-saving) if expired."""
    if not os.path.exists(token_file):
        raise RuntimeError(
            f"OAuth token file not found: {token_file}. "
            "Run `python -m slack_sheet_sync.google_oauth_setup` once to create it."
        )

    creds = UserCredentials.from_authorized_user_file(token_file, SCOPES)
    if creds.valid:
        return creds

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(token_file, "w") as handle:
            handle.write(creds.to_json())
        return creds

    raise RuntimeError(
        f"OAuth credentials in {token_file} are invalid and cannot be refreshed. "
        "Re-run `python -m slack_sheet_sync.google_oauth_setup`."
    )
