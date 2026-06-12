"""Auth client construction: service-account vs OAuth, token refresh and errors."""

from __future__ import annotations

import types

import pytest

from slack_sheet_sync import google_auth


def _cfg(**kwargs) -> types.SimpleNamespace:
    base = {
        "auth_mode": "service_account",
        "google_credentials_file": "",
        "google_oauth_token_file": "",
    }
    base.update(kwargs)
    return types.SimpleNamespace(**base)


def test_service_account_mode_loads_key_file(monkeypatch):
    seen = {}

    def fake_loader(path, scopes):
        seen["path"] = path
        seen["scopes"] = scopes
        return "SA_CREDS"

    monkeypatch.setattr(
        google_auth.ServiceAccountCredentials, "from_service_account_file", fake_loader
    )
    monkeypatch.setattr(google_auth.gspread, "authorize", lambda creds: ("client", creds))

    client = google_auth.build_client(_cfg(google_credentials_file="/x/sa.json"))

    assert client == ("client", "SA_CREDS")
    assert seen["path"] == "/x/sa.json"
    assert seen["scopes"] == google_auth.SCOPES


def test_oauth_mode_uses_valid_token(monkeypatch, tmp_path):
    token = tmp_path / "t.json"
    token.write_text("{}")
    creds = types.SimpleNamespace(valid=True)
    monkeypatch.setattr(
        google_auth.UserCredentials, "from_authorized_user_file", lambda f, s: creds
    )
    monkeypatch.setattr(google_auth.gspread, "authorize", lambda c: ("client", c))

    client = google_auth.build_client(_cfg(auth_mode="oauth", google_oauth_token_file=str(token)))

    assert client == ("client", creds)


def test_oauth_refreshes_and_resaves_expired_token(monkeypatch, tmp_path):
    token = tmp_path / "t.json"
    token.write_text("{}")

    class FakeCreds:
        valid = False
        expired = True
        refresh_token = "r"

        def __init__(self):
            self.refreshed = False

        def refresh(self, _request):
            self.refreshed = True

        def to_json(self):
            return '{"refreshed": true}'

    creds = FakeCreds()
    monkeypatch.setattr(
        google_auth.UserCredentials, "from_authorized_user_file", lambda f, s: creds
    )
    monkeypatch.setattr(google_auth.gspread, "authorize", lambda c: c)

    google_auth.build_client(_cfg(auth_mode="oauth", google_oauth_token_file=str(token)))

    assert creds.refreshed is True
    assert token.read_text() == '{"refreshed": true}'  # refreshed token persisted


def test_oauth_missing_token_file_raises(tmp_path):
    missing = tmp_path / "nope.json"
    with pytest.raises(RuntimeError, match="not found"):
        google_auth.build_client(_cfg(auth_mode="oauth", google_oauth_token_file=str(missing)))


def test_oauth_unrefreshable_token_raises(monkeypatch, tmp_path):
    token = tmp_path / "t.json"
    token.write_text("{}")
    creds = types.SimpleNamespace(valid=False, expired=False, refresh_token=None)
    monkeypatch.setattr(
        google_auth.UserCredentials, "from_authorized_user_file", lambda f, s: creds
    )

    with pytest.raises(RuntimeError, match="cannot be refreshed"):
        google_auth.build_client(_cfg(auth_mode="oauth", google_oauth_token_file=str(token)))
