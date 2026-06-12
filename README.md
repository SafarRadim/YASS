# YASS — Yet Another Slack Syncer

A small, self-hostable service that keeps an external destination in sync with a Slack
workspace's membership and profile data. It polls Slack on a schedule and reconciles the
differences — no public URL, webhook, or Socket Mode to manage.

The current sync target is **Google Sheets**: members become rows, and selected profile
fields are kept up to date. The reconcile core is destination-agnostic, so other targets
(a database, a CSV, an HTTP endpoint) can be added behind the same poll-and-diff loop.

**Google Sheets sync at a glance:**

- **New member joins Slack** → a new row is appended.
- **Email / phone / section change** → the matching cells are updated.

Detection is poll-only (one job does everything by diffing `users.list` against the
destination), so there is nothing inbound to expose. Rows are keyed by Slack user id, and
members removed from Slack are left in place (never auto-deleted).

> The Python package is named `slack_sheet_sync` — that's the module you invoke and the
> systemd unit you install. "YASS" is the project name.

## Sheet layout

| slack_id | name | email | phone | section | updated_at |
|----------|------|-------|-------|---------|------------|

The header is created automatically on first run.

Slack is the source of truth; the sheet is a downstream projection. Notes:

- **Deleting a row** doesn't remove anyone — if they're still in Slack, the next poll
  re-adds them at the bottom. Remove people in Slack instead. Appends always target the
  first row below all existing content, so even a leftover blank row (e.g. from clearing
  cells instead of deleting the row) never causes a misplaced or duplicated append.
- **Manually editing** a synced cell (name/email/phone/section) gets overwritten on the
  next poll if it differs from Slack. Extra columns you add to the right of `updated_at`
  are never touched.
- Users removed from Slack keep their last-synced row (we never auto-delete data).

## Setup

### 1. Slack app (ask a workspace admin)
Create an app at <https://api.slack.com/apps>, install it to the workspace, and grant the
bot these scopes:

- `users:read`
- `users:read.email`  *(required to read email addresses)*
- `users.profile:read`  *(required to read the custom "section" field)*

Copy the **Bot User OAuth Token** (`xoxb-…`).

### 2. Google access

Pick one auth mode and set `GOOGLE_AUTH_MODE` in `.env` accordingly.

**Mode A — service account (default, `GOOGLE_AUTH_MODE=service_account`)**
1. In Google Cloud, create a service account and download its JSON key.
2. Enable the **Google Sheets API** for the project.
3. Share the target spreadsheet with the service account's email (Editor access).

Simplest, but the service account is an *external* identity — if your org forbids
external sharing, this share is blocked. In that case use Mode B.

**Mode B — user OAuth (`GOOGLE_AUTH_MODE=oauth`)**

The app acts as a real user who already has access to the sheet (e.g. via a Google Group
or shared folder), so it inherits that access and sidesteps external-sharing limits — no
workspace-admin cooperation needed.

1. In a Google Cloud project you own, enable the **Google Sheets API** and create an
   **OAuth client ID** of type *Desktop app*; download its client-secrets JSON.
2. Point `GOOGLE_OAUTH_CLIENT_FILE` and `GOOGLE_OAUTH_TOKEN_FILE` at that file and a
   token path in `.env`.
3. On a machine **with a browser**, signed in as a user who can edit the sheet, run the
   one-time consent:
   ```bash
   GOOGLE_AUTH_MODE=oauth uv run python -m slack_sheet_sync.google_oauth_setup
   ```
   This writes the authorized-user token to `GOOGLE_OAUTH_TOKEN_FILE`.
4. Copy that token file to the server (chmod 600). The service refreshes it automatically
   from then on.

> Caveat: some orgs also restrict third-party OAuth apps. If consent is denied for an
> unverified app, there's no path without admin help.

### 3. Configure
```bash
cp .env.example .env
# edit .env with your token, paths, and spreadsheet id
```

Find the opaque id of your "section" profile field:
```bash
python -m slack_sheet_sync.find_field_id
```
Put the printed FIELD ID into `SECTION_FIELD_ID` in `.env`.

### 4. Install & run

This project uses [uv](https://docs.astral.sh/uv/). `uv sync` creates `.venv` and
installs runtime + dev dependencies from the lockfile.

```bash
uv sync

# dry run: log intended changes, write nothing (great for first verification)
uv run python -m slack_sheet_sync --dry-run

# one-off test run
uv run python -m slack_sheet_sync --once

# run the poll loop
uv run python -m slack_sheet_sync
```

## Deploy (ARM instance, systemd timer)

The service runs as a **oneshot `--once` sync fired by a systemd timer** once a day at
midnight (lighter than an always-on loop, and crash-clean — each run is a fresh process).

First-time install (run as your normal user; it sudos only for the systemd bits):
```bash
./deploy/setup.sh
```
This secures `.env` / `service-account.json` (chmod 600), builds the venv with
`uv sync`, fills the unit template with your user + paths, installs
`slack-sheet-sync.service` + `slack-sheet-sync.timer`, and enables the timer.

Updating an existing deployment after a code change:
```bash
./deploy/deploy.sh        # git pull + uv sync + one immediate verified run
```

Handy commands:
```bash
systemctl list-timers slack-sheet-sync.timer   # when it next fires
sudo systemctl start slack-sheet-sync.service  # run one sync right now
journalctl -u slack-sheet-sync.service -f      # follow logs
```

> Schedule is controlled by `OnCalendar` in `deploy/slack-sheet-sync.timer` (default:
> `*-*-* 00:00:00`, i.e. midnight **local time**), **not** by `POLL_INTERVAL_SECONDS`
> (that env var only applies to the always-on loop mode, `python -m slack_sheet_sync`
> without `--once`). To change the schedule, edit the timer and re-run `./deploy/setup.sh`.
> Confirm the box's timezone with `timedatectl` so "midnight" means what you expect.

## Development
```bash
uv sync                # installs dev tools (ruff, pytest) too
uv run pytest          # run the test suite
uv run ruff check .    # lint
uv run ruff format .   # format
```
