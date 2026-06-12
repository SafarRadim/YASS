"""Test doubles for Slack and Google Sheets, plus shared fixtures."""

from __future__ import annotations

import pytest

from slack_sheet_sync.sheet_sink import HEADER


class FakeWorksheet:
    """Minimal stand-in for gspread.Worksheet covering what sync_members uses.

    Records every write call in `self.calls` so tests can assert exact ranges/values.
    """

    def __init__(self, rows: list[list[str]], row_count: int = 100):
        self._rows = rows
        self.row_count = row_count
        self.calls: list[tuple] = []

    def get_all_values(self) -> list[list[str]]:
        return self._rows

    def batch_update(self, data, **_kwargs) -> None:
        self.calls.append(("batch_update", data))

    def add_rows(self, rows: int) -> None:
        self.calls.append(("add_rows", rows))
        self.row_count += rows

    def update(self, values, range_name, **_kwargs) -> None:
        self.calls.append(("update", range_name, values))

    # Convenience accessors for assertions -----------------------------------
    @property
    def updates(self) -> list[tuple]:
        return [c for c in self.calls if c[0] in ("batch_update", "update")]

    @property
    def append_call(self) -> tuple | None:
        for call in self.calls:
            if call[0] == "update" and call[1].startswith("A"):
                return call
        return None


class FakeSlackResponse(dict):
    """A dict that also supports the .get(...) members/response_metadata shape."""


class FakeWebClient:
    """Stand-in for slack_sdk.WebClient.users_list with cursor pagination."""

    def __init__(self, pages: list[dict]):
        # Each page is a dict like {"members": [...], "next_cursor": "abc" | ""}.
        self._pages = pages
        self.seen_cursors: list[str | None] = []

    def users_list(self, limit: int = 200, cursor: str | None = None):  # noqa: ARG002
        self.seen_cursors.append(cursor)
        index = 0 if cursor is None else int(cursor)
        page = self._pages[index]
        next_index = index + 1
        next_cursor = str(next_index) if next_index < len(self._pages) else ""
        return {
            "members": page["members"],
            "response_metadata": {"next_cursor": next_cursor},
        }


@pytest.fixture
def header_row() -> list[str]:
    return list(HEADER)


def make_user(uid: str, **profile) -> dict:
    """Build a Slack user payload with a profile, defaulting the common fields."""
    base = {
        "real_name": profile.pop("real_name", ""),
        "email": profile.pop("email", ""),
        "phone": profile.pop("phone", ""),
    }
    base.update(profile)  # allows passing fields={...}, etc.
    return {"id": uid, "profile": base}
