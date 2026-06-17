"""One-shot entry point for GitHub Actions (free, no server).

Each scheduled run:
  1. processes any filter-menu taps you made since last run, and
  2. scrapes OLX + Otodom and sends new matching listings.

The button menu therefore works on the free cron host too — it just updates
on the next run (a few minutes) instead of instantly.

Run with:  python -m bot.cron          (normal)
           python -m bot.cron --prime  (record current listings, send nothing)
"""
from __future__ import annotations

import argparse
import logging
import os

from .app import InteractiveBot
from .engine import poll_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bot.cron")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prime", action="store_true",
                    help="record current listings without sending (run once)")
    args = ap.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.")

    bot = InteractiveBot(token, chat_id)

    # 1) handle filter menu interactions
    try:
        bot.drain_updates()
    except Exception:  # noqa: BLE001
        log.exception("Draining updates failed (continuing to scrape)")

    # 2) scrape + notify
    if args.prime or not bot.store.has_any():
        poll_cycle(bot.settings, bot.store, None, prime=True)
        bot.notifier.send_text(
            "✅ Бот запущено. Відстежую нові оголошення за вашими фільтрами. "
            "Надішліть /filters, щоб змінити пошук."
        )
    elif not bot.settings.paused:
        poll_cycle(bot.settings, bot.store, bot.notifier)
    else:
        log.info("Alerts paused; skipping scrape this run.")


if __name__ == "__main__":
    main()
