#!/usr/bin/env bash
# Update an existing deployment: pull code, sync deps, run one sync now.
# The timer keeps firing on its own; each fire launches a fresh process, so new code
# is picked up automatically — this just pulls and gives you an immediate verified run.
set -euo pipefail

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$APP_DIR"

git pull --ff-only
uv sync --frozen

# Reload in case the unit/timer files changed in this pull.
sudo systemctl daemon-reload
sudo systemctl restart slack-sheet-sync.timer

# Run once right now with the new code and show the result.
sudo systemctl start slack-sheet-sync.service
echo
echo "Deployed. Recent logs:"
journalctl -u slack-sheet-sync.service -n 20 --no-pager
