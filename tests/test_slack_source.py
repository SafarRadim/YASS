"""Slack reading: field extraction, bot/deleted filtering, cursor pagination."""

from __future__ import annotations

from conftest import FakeWebClient, make_user

from slack_sheet_sync.slack_source import fetch_members

SECTION = "Xf0SECTION"


def test_extracts_section_from_custom_profile_field():
    user = make_user(
        "U1",
        real_name="Alice",
        email="alice@x.com",
        phone="123",
        fields={SECTION: {"value": "Engineering", "alt": ""}},
    )
    client = FakeWebClient([{"members": [user]}])

    (member,) = fetch_members(client, SECTION)

    assert member.slack_id == "U1"
    assert member.name == "Alice"
    assert member.email == "alice@x.com"
    assert member.phone == "123"
    assert member.section == "Engineering"


def test_missing_section_field_is_empty_string():
    client = FakeWebClient([{"members": [make_user("U1", real_name="Al")]}])

    (member,) = fetch_members(client, SECTION)

    assert member.section == ""


def test_bots_deleted_and_slackbot_are_skipped():
    members = [
        make_user("U1", real_name="Real"),
        {"id": "B1", "is_bot": True, "profile": {}},
        {"id": "U2", "deleted": True, "profile": {}},
        {"id": "USLACKBOT", "profile": {}},
    ]
    client = FakeWebClient([{"members": members}])

    result = fetch_members(client, SECTION)

    assert [m.slack_id for m in result] == ["U1"]


def test_pagination_follows_cursor_across_pages():
    pages = [
        {"members": [make_user("U1", real_name="One")]},
        {"members": [make_user("U2", real_name="Two")]},
        {"members": [make_user("U3", real_name="Three")]},
    ]
    client = FakeWebClient(pages)

    result = fetch_members(client, SECTION)

    assert [m.slack_id for m in result] == ["U1", "U2", "U3"]
    # First call with no cursor, then follows "1" and "2".
    assert client.seen_cursors == [None, "1", "2"]


def test_values_are_stripped():
    user = make_user(
        "U1",
        real_name="  Spacey  ",
        email=" e@x.com ",
        fields={SECTION: {"value": "  Ops  "}},
    )
    client = FakeWebClient([{"members": [user]}])

    (member,) = fetch_members(client, SECTION)

    assert member.name == "Spacey"
    assert member.email == "e@x.com"
    assert member.section == "Ops"
