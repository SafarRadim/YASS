"""Reconcile Slack members into a Google Sheet worksheet.

The worksheet is keyed by Slack user id (first column). New members are appended;
existing members get only their changed cells updated. Rows for users no longer in
Slack are left untouched (we never delete data automatically).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

from .slack_source import Member

log = logging.getLogger("slack_sheet_sync")

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Column order in the sheet. slack_id is the stable key and must stay first.
HEADER = ["slack_id", "name", "email", "phone", "section", "updated_at"]
_FIELDS = ("name", "email", "phone", "section")
# Rightmost column letter for the header (A=slack_id ... F=updated_at). Assumes <=26 cols.
HEADER_LAST_COL = chr(ord("A") + len(HEADER) - 1)


def open_worksheet(
    credentials_file: str, spreadsheet_id: str, worksheet_name: str
) -> gspread.Worksheet:
    creds = Credentials.from_service_account_file(credentials_file, scopes=SCOPES)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(spreadsheet_id)
    try:
        worksheet = spreadsheet.worksheet(worksheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(worksheet_name, rows=100, cols=len(HEADER))

    _ensure_header(worksheet)
    return worksheet


def _ensure_header(worksheet: gspread.Worksheet) -> None:
    existing = worksheet.row_values(1)
    if existing[: len(HEADER)] != HEADER:
        worksheet.update([HEADER], "A1", value_input_option="RAW")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def sync_members(
    worksheet: gspread.Worksheet, members: list[Member], dry_run: bool = False
) -> dict[str, int]:
    """Append new members and update changed fields. Returns counts for logging.

    When dry_run is True, no writes are made; intended changes are logged instead.
    """
    rows = worksheet.get_all_values()
    # Map slack_id -> 1-based sheet row number (skip header at row 1).
    row_by_id: dict[str, int] = {}
    cells_by_id: dict[str, list[str]] = {}
    for offset, row in enumerate(rows[1:], start=2):
        if row and row[0]:
            row_by_id[row[0]] = offset
            cells_by_id[row[0]] = row

    updates: list[dict] = []
    appends: list[list[str]] = []
    changed = 0

    prefix = "[dry-run] " if dry_run else ""

    for member in members:
        record = [member.name, member.email, member.phone, member.section]
        if member.slack_id not in row_by_id:
            appends.append([member.slack_id, *record, _now()])
            log.info("%sADD %s (%s)", prefix, member.name or "?", member.slack_id)
            continue

        existing = cells_by_id[member.slack_id]
        # Compare columns B..E (indices 1..4) against current Slack values.
        current = existing[1 : 1 + len(_FIELDS)]
        current += [""] * (len(_FIELDS) - len(current))  # pad short rows
        if current != record:
            row_num = row_by_id[member.slack_id]
            updates.append(
                {
                    "range": f"B{row_num}:F{row_num}",
                    "values": [[*record, _now()]],
                }
            )
            changed += 1
            diff = ", ".join(
                f"{name}: {old!r} -> {new!r}"
                for name, old, new in zip(_FIELDS, current, record, strict=True)
                if old != new
            )
            log.info("%sUPDATE row %d %s (%s)", prefix, row_num, member.slack_id, diff)

    if dry_run:
        log.info("[dry-run] no writes made; would add %d, update %d", len(appends), changed)
    else:
        if updates:
            worksheet.batch_update(updates, value_input_option="RAW")
        if appends:
            _append_at_bottom(worksheet, appends, first_empty_row=len(rows) + 1)

    return {"added": len(appends), "updated": changed, "total_slack": len(members)}


def _append_at_bottom(
    worksheet: gspread.Worksheet, new_rows: list[list[str]], first_empty_row: int
) -> None:
    """Write new rows at an explicit position below all existing content.

    Unlike append_rows (which relies on the Sheets API's table detection and can land
    inside a mid-sheet blank-row gap), this targets first_empty_row directly. Because
    get_all_values() counts mid-table blanks in its length, first_empty_row is always
    below every existing row, so appends never collide with stray gaps.
    """
    last_row = first_empty_row + len(new_rows) - 1
    if last_row > worksheet.row_count:
        worksheet.add_rows(last_row - worksheet.row_count)
    range_name = f"A{first_empty_row}:{HEADER_LAST_COL}{last_row}"
    worksheet.update(new_rows, range_name, value_input_option="RAW")
