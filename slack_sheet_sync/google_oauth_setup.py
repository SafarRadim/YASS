"""One-time interactive OAuth consent for the ``oauth`` auth mode.

Run this on a machine **with a browser** (e.g. your laptop), signed in as a Google user
who already has edit access to the target sheet:

    GOOGLE_AUTH_MODE=oauth python -m slack_sheet_sync.google_oauth_setup

It opens a browser, asks you to grant the Sheets scope, and writes an authorized-user
token to GOOGLE_OAUTH_TOKEN_FILE. Copy that token file to the server (alongside .env);
the service then runs headlessly, refreshing the token automatically.
"""

from __future__ import annotations

import sys

from google_auth_oauthlib.flow import InstalledAppFlow

from .config import Config, ConfigError
from .google_auth import SCOPES


def main() -> int:
    try:
        config = Config.from_env()
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2

    if config.auth_mode != "oauth":
        print("GOOGLE_AUTH_MODE is not 'oauth'; nothing to do.", file=sys.stderr)
        return 1

    flow = InstalledAppFlow.from_client_secrets_file(config.google_oauth_client_file, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(config.google_oauth_token_file, "w") as handle:
        handle.write(creds.to_json())

    print(f"Saved authorized-user token to {config.google_oauth_token_file}")
    print("Copy this file to the server and keep it secret (chmod 600).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
