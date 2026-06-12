"""Helper: list the workspace's custom profile fields and their opaque ids.

Run once during setup to discover the SECTION_FIELD_ID:

    python -m slack_sheet_sync.find_field_id

Requires SLACK_BOT_TOKEN in the environment (or .env). The token needs the
users.profile:read scope. team.profile.get returns the field definitions.
"""

from __future__ import annotations

import sys

from slack_sdk import WebClient

from .config import _require


def main() -> int:
    client = WebClient(token=_require("SLACK_BOT_TOKEN"))
    response = client.team_profile_get()
    fields = (response.get("profile") or {}).get("fields") or []
    if not fields:
        print("No custom profile fields are defined in this workspace.")
        return 1

    print(f"{'FIELD ID':<14}  {'LABEL':<30}  TYPE")
    print("-" * 60)
    for field in fields:
        print(f"{field.get('id', ''):<14}  {field.get('label', ''):<30}  {field.get('type', '')}")
    print("\nCopy the FIELD ID of your 'section' field into SECTION_FIELD_ID in .env")
    return 0


if __name__ == "__main__":
    sys.exit(main())
