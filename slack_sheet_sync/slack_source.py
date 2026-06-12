"""Read workspace members and their profile fields from Slack."""

from __future__ import annotations

from dataclasses import dataclass

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


@dataclass(frozen=True)
class Member:
    slack_id: str
    name: str
    email: str
    phone: str
    section: str


def _extract_section(profile: dict, section_field_id: str) -> str:
    """Custom profile fields live under profile['fields'] keyed by opaque id."""
    fields = profile.get("fields") or {}
    field = fields.get(section_field_id) or {}
    return (field.get("value") or "").strip()


def fetch_members(client: WebClient, section_field_id: str) -> list[Member]:
    """Return all human, active members. Bots, apps and deactivated users are skipped."""
    members: list[Member] = []
    cursor: str | None = None

    while True:
        try:
            response = client.users_list(limit=200, cursor=cursor)
        except SlackApiError as exc:
            raise RuntimeError(f"Slack users.list failed: {exc.response['error']}") from exc

        for user in response.get("members", []):
            if user.get("is_bot") or user.get("deleted") or user.get("id") == "USLACKBOT":
                continue

            profile = user.get("profile") or {}
            members.append(
                Member(
                    slack_id=user["id"],
                    name=(profile.get("real_name") or user.get("name") or "").strip(),
                    email=(profile.get("email") or "").strip(),
                    phone=(profile.get("phone") or "").strip(),
                    section=_extract_section(profile, section_field_id),
                )
            )

        cursor = (response.get("response_metadata") or {}).get("next_cursor")
        if not cursor:
            break

    return members
