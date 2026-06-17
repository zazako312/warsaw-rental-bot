"""Cron / one-shot entry point (filters from config.yaml).

For the interactive button-menu bot, run `python -m bot.app` instead.
"""
from __future__ import annotations

import argparse
import logging
import time

from .config import load_config
from .store import SeenStore
from .notifier import Telegram
from .engine import poll_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bot")


def main():
    ap = argparse.ArgumentParser(description="Warsaw rental Telegram bot (cron mode)")
    ap.add_argument("--once", action="store_true", help="run a single poll cycle (default)")
    ap.add_argument("--loop", action="store_true", help="run continuously")
    ap.add_argument("--prime", action="store_true",
                    help="record current listings WITHOUT sending (run once after setup)")
    ap.add_argument("--dry-run", action="store_true", help="scrape & filter but do not send")
    args = ap.parse_args()

    cfg = load_config()
    store = SeenStore()

    telegram = None
    if not args.dry_run:
        cfg.validate_secrets()
        telegram = Telegram(cfg.telegram_token, cfg.telegram_chat_id)

    if args.loop:
        log.info("Loop mode: polling every %d min", cfg.interval_minutes)
        while True:
            try:
                poll_cycle(cfg, store, telegram)
            except Exception:  # noqa: BLE001
                log.exception("Cycle failed; retrying next interval")
            time.sleep(cfg.interval_minutes * 60)
    else:
        poll_cycle(cfg, store, telegram, prime=args.prime)


if __name__ == "__main__":
    main()
