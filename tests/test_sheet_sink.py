"""Reconcile logic: adds, updates, dry-run, gap-safe and grid-growing appends."""

from __future__ import annotations

from conftest import FakeWorksheet

from slack_sheet_sync.sheet_sink import HEADER
from slack_sheet_sync.slack_source import Member


def _sheet(*data_rows: list[str]) -> list[list[str]]:
    return [list(HEADER), *[list(r) for r in data_rows]]


def test_new_member_is_appended_at_bottom():
    ws = FakeWorksheet(_sheet(["U1", "Al", "a@x.com", "", "Eng", "t"]))
    from slack_sheet_sync.sheet_sink import sync_members

    stats = sync_members(ws, [Member("U2", "Bo", "b@x.com", "", "Ops")])

    assert stats == {"added": 1, "updated": 0, "total_slack": 1}
    # U1 unchanged -> no batch_update; U2 appended at row 3 (below header + 1 data row).
    assert ws.append_call == (
        "update",
        "A3:F3",
        [["U2", "Bo", "b@x.com", "", "Ops", _ts(ws)]],
    )


def test_changed_fields_produce_a_batch_update_with_diff():
    ws = FakeWorksheet(_sheet(["U1", "Al", "a@x.com", "", "Eng", "old"]))
    from slack_sheet_sync.sheet_sink import sync_members

    stats = sync_members(ws, [Member("U1", "Al", "a@x.com", "999", "Engineering")])

    assert stats["updated"] == 1 and stats["added"] == 0
    batch = next(c for c in ws.calls if c[0] == "batch_update")
    (data,) = batch[1:]
    assert data[0]["range"] == "B2:F2"
    assert data[0]["values"] == [["Al", "a@x.com", "999", "Engineering", _ts(ws)]]


def test_unchanged_member_writes_nothing():
    ws = FakeWorksheet(_sheet(["U1", "Al", "a@x.com", "555", "Eng", "t"]))
    from slack_sheet_sync.sheet_sink import sync_members

    stats = sync_members(ws, [Member("U1", "Al", "a@x.com", "555", "Eng")])

    assert stats == {"added": 0, "updated": 0, "total_slack": 1}
    assert ws.calls == []


def test_dry_run_makes_no_writes():
    ws = FakeWorksheet(_sheet(["U1", "Al", "a@x.com", "", "Eng", "t"]))
    from slack_sheet_sync.sheet_sink import sync_members

    members = [
        Member("U1", "Al", "a@x.com", "999", "Engineering"),  # would update
        Member("U2", "Bo", "b@x.com", "", "Ops"),  # would add
    ]
    stats = sync_members(ws, members, dry_run=True)

    assert stats == {"added": 1, "updated": 1, "total_slack": 2}
    assert ws.calls == []  # nothing written


def test_append_skips_mid_sheet_blank_gap():
    # Row 2 is a leftover blank (cells cleared, row not deleted); real data at row 3.
    sheet = [list(HEADER), ["", "", "", "", "", ""], ["U2", "Bo", "b@x.com", "555", "Design", "t"]]
    ws = FakeWorksheet(sheet)
    from slack_sheet_sync.sheet_sink import sync_members

    sync_members(
        ws,
        [
            Member("U2", "Bo", "b@x.com", "555", "Design"),  # unchanged
            Member("U9", "Dave", "d@x.com", "", "Ops"),  # new
        ],
    )

    # Must land at row 4 (below all content), never inside the row-2 gap.
    assert ws.append_call is not None
    assert ws.append_call[1] == "A4:F4"


def test_append_grows_grid_when_too_small():
    ws = FakeWorksheet(_sheet(["U1", "Al", "a@x.com", "", "Eng", "t"]), row_count=2)
    from slack_sheet_sync.sheet_sink import sync_members

    sync_members(ws, [Member("U2", "Bo", "b@x.com", "", "Ops")])

    assert ("add_rows", 1) in ws.calls
    # add_rows must precede the write.
    assert ws.calls.index(("add_rows", 1)) < ws.calls.index(ws.append_call)


def test_multiple_new_members_written_in_one_contiguous_block():
    ws = FakeWorksheet(_sheet(["U1", "Al", "a@x.com", "", "Eng", "t"]))
    from slack_sheet_sync.sheet_sink import sync_members

    sync_members(
        ws,
        [
            Member("U1", "Al", "a@x.com", "", "Eng"),  # unchanged
            Member("U2", "Bo", "b@x.com", "", "Ops"),  # new
            Member("U3", "Cy", "c@x.com", "", "Ops"),  # new
        ],
    )

    assert ws.append_call[1] == "A3:F4"
    assert [row[0] for row in ws.append_call[2]] == ["U2", "U3"]


def _ts(ws: FakeWorksheet) -> str:
    """Pull the timestamp the code actually wrote, so tests don't race the clock."""
    for call in ws.calls:
        if call[0] == "update" and call[1].startswith("A"):
            return call[2][0][-1]
        if call[0] == "batch_update":
            return call[1][0]["values"][0][-1]
    raise AssertionError("no write call recorded")
