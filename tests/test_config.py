"""Config validation: auth-mode selection and per-mode required variables."""

from __future__ import annotations

import pytest

from slack_sheet_sync.config import Config, ConfigError

BASE = {
    "SLACK_BOT_TOKEN": "xoxb-x",
    "SPREADSHEET_ID": "sid",
    "SECTION_FIELD_ID": "Xf1",
}
_AUTH_VARS = (
    "GOOGLE_AUTH_MODE",
    "GOOGLE_CREDENTIALS_FILE",
    "GOOGLE_OAUTH_CLIENT_FILE",
    "GOOGLE_OAUTH_TOKEN_FILE",
    "WORKSHEET_NAME",
    "POLL_INTERVAL_SECONDS",
)


@pytest.fixture
def env(monkeypatch):
    for key in _AUTH_VARS:
        monkeypatch.delenv(key, raising=False)
    for key, value in BASE.items():
        monkeypatch.setenv(key, value)
    return monkeypatch


def test_defaults_to_service_account(env):
    env.setenv("GOOGLE_CREDENTIALS_FILE", "./sa.json")
    cfg = Config.from_env()
    assert cfg.auth_mode == "service_account"
    assert cfg.google_credentials_file == "./sa.json"
    assert cfg.worksheet_name == "Members"


def test_service_account_requires_credentials_file(env):
    with pytest.raises(ConfigError, match="GOOGLE_CREDENTIALS_FILE"):
        Config.from_env()


def test_oauth_requires_client_then_token(env):
    env.setenv("GOOGLE_AUTH_MODE", "oauth")
    with pytest.raises(ConfigError, match="GOOGLE_OAUTH_CLIENT_FILE"):
        Config.from_env()

    env.setenv("GOOGLE_OAUTH_CLIENT_FILE", "./c.json")
    with pytest.raises(ConfigError, match="GOOGLE_OAUTH_TOKEN_FILE"):
        Config.from_env()

    env.setenv("GOOGLE_OAUTH_TOKEN_FILE", "./t.json")
    cfg = Config.from_env()
    assert cfg.auth_mode == "oauth"
    assert cfg.google_oauth_client_file == "./c.json"
    assert cfg.google_oauth_token_file == "./t.json"


def test_oauth_mode_does_not_require_service_account_file(env):
    env.setenv("GOOGLE_AUTH_MODE", "oauth")
    env.setenv("GOOGLE_OAUTH_CLIENT_FILE", "./c.json")
    env.setenv("GOOGLE_OAUTH_TOKEN_FILE", "./t.json")
    cfg = Config.from_env()  # must not raise about GOOGLE_CREDENTIALS_FILE
    assert cfg.google_credentials_file == ""


def test_invalid_auth_mode_is_rejected(env):
    env.setenv("GOOGLE_AUTH_MODE", "banana")
    with pytest.raises(ConfigError, match="GOOGLE_AUTH_MODE"):
        Config.from_env()


def test_auth_mode_is_case_insensitive(env):
    env.setenv("GOOGLE_AUTH_MODE", "OAuth")
    env.setenv("GOOGLE_OAUTH_CLIENT_FILE", "./c.json")
    env.setenv("GOOGLE_OAUTH_TOKEN_FILE", "./t.json")
    assert Config.from_env().auth_mode == "oauth"
