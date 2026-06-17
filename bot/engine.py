"""One poll cycle, shared by the cron entry point and the interactive bot."""
from __future__ import annotations

import logging

from .http import make_session
from .scrapers import olx, otodom
from .filters import apply as apply_filters
from .details import enrich

log = logging.getLogger("bot.engine")


def poll_cycle(settings, store, telegram, *, prime: bool = False) -> int:
    """Scrape -> filter -> dedup -> enrich -> notify -> persist. Returns # sent."""
    session = make_session()

    listings = []
    listings += olx.scrape(settings, session)
    listings += otodom.scrape(settings, session)

    unique = {l.key: l for l in listings}
    listings = apply_filters(list(unique.values()), settings)

    new = [l for l in listings if not store.has(l.key)]
    log.info("Found %d matching, %d new", len(listings), len(new))

    if prime:
        for l in listings:
            store.add(l.key)
        store.save()
        log.info("Primed with %d existing listings (nothing sent)", len(listings))
        return 0

    new = new[: settings.max_per_cycle]

    # Enrich detail pages only for what we'll actually send.
    for l in new:
        enrich(l, session)

    # Pets filter needs the detail page, so it runs here (post-enrich).
    if getattr(settings, "pets_only", False):
        new = [l for l in new if l.pets]

    sent = 0
    if new and telegram:
        sent = telegram.broadcast(new)
        log.info("Sent %d notifications", sent)

    for l in new:
        store.add(l.key)
    store.save()
    return sent
