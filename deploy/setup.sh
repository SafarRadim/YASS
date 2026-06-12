#!/usr/bin/env bash
# First-time install on the ARM box: secure secrets, build the venv, and install the
# systemd timer + oneshot service (paths/user are filled in automatically).
#
# Run as your normal user (it uses sudo only for the systemd parts):
#   ./deploy/setup.sh
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RUN_USER="${SUDO_USER:-$USER}"

echo "App dir: $APP_DIR"
echo "Run as:  $RUN_USER"

# 1. Secure whichever secret files are present (which exist depends on the auth mode).
for f in .env service-account.json oauth-client.json oauth-token.json; do
    if [ -f "$APP_DIR/$f" ]; then
        chmod 600 "$APP_DIR/$f"
        echo "secured $f (600)"
    fi
done
if [ ! -f "$APP_DIR/.env" ]; then
    echo "WARNING: $APP_DIR/.env not found — create it (cp .env.example .env) before the first run"
fi

# 2. Build the virtualenv from the lockfile if it isn't there yet.
if [ ! -x "$APP_DIR/.venv/bin/python" ]; then
    echo "creating venv with uv sync..."
    (cd "$APP_DIR" && uv sync --frozen)
fi

# 3. Render the oneshot unit from the template and install both units.
rendered="$(mktemp)"
sed -e "s|__APP_DIR__|$APP_DIR|g" -e "s|__USER__|$RUN_USER|g" \
    "$APP_DIR/deploy/slack-sheet-sync.service.template" >"$rendered"

sudo cp "$rendered" /etc/systemd/system/slack-sheet-sync.service
sudo cp "$APP_DIR/deploy/slack-sheet-sync.timer" /etc/systemd/system/slack-sheet-sync.timer
rm -f "$rendered"

sudo systemctl daemon-reload
sudo systemctl enable --now slack-sheet-sync.timer

echo
echo "Installed. Schedule:"
systemctl list-timers slack-sheet-sync.timer --no-pager
echo
echo "Run one sync immediately:  sudo systemctl start slack-sheet-sync.service"
echo "Follow logs:               journalctl -u slack-sheet-sync.service -f"
