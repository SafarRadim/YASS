"""Entrypoint: poll Slack on an interval and reconcile into the Google Sheet.

Run once:    python -m slack_sheet_sync --once
Run forever: python -m slack_sheet_sync
"""

from __future__ import annotations

import argparse
import logging
import sys
import time

from slack_sdk import WebClient

from .config import Config, ConfigError
from .sheet_sink import open_worksheet, sync_members
from .slack_source import fetch_members

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("slack_sheet_sync")


def run_once(config: Config, dry_run: bool = False) -> None:
    client = WebClient(token=config.slack_bot_token)
    worksheet = open_worksheet(config)
    members = fetch_members(client, config.section_field_id)
    stats = sync_members(worksheet, members, dry_run=dry_run)
    log.info(
        "sync complete: %d in Slack, %d added, %d updated",
        stats["total_slack"],
        stats["added"],
        stats["updated"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="slack_sheet_sync")
    parser.add_argument("--once", action="store_true", help="Run a single sync and exit.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log intended changes without writing to the sheet. Implies --once.",
    )
    args = parser.parse_args(argv)

    try:
        config = Config.from_env()
    except ConfigError as exc:
        log.error("%s", exc)
        return 2

    if args.dry_run:
        run_once(config, dry_run=True)
        return 0

    if args.once:
        run_once(config)
        return 0

    log.info("starting poll loop, interval=%ds", config.poll_interval_seconds)
    while True:
        try:
            run_once(config)
        except Exception:  # noqa: BLE001 - keep the daemon alive across transient failures
            log.exception("sync failed, will retry next interval")
        time.sleep(config.poll_interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
