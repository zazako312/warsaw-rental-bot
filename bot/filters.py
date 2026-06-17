"""Filtering rules applied to scraped listings before notifying."""
from __future__ import annotations

import logging

from .models import Listing

log = logging.getLogger("bot.filters")


def _keep(lst: Listing, cfg) -> bool:
    title = (lst.title or "").lower()

    # Short-term / scam keyword exclusion.
    for kw in cfg.exclude_keywords:
        if kw and kw in title:
            return False

    if lst.price is not None:
        if cfg.price_sanity_min and lst.price < cfg.price_sanity_min:
            return False
        if cfg.price_min and lst.price < cfg.price_min:
            return False
        if cfg.price_max and lst.price > cfg.price_max:
            return False

    if cfg.area_min and lst.area is not None and lst.area < cfg.area_min:
        return False

    # Rooms filter only applied when we actually know the room count.
    if cfg.rooms and lst.rooms is not None and lst.rooms not in cfg.rooms:
        return False

    # District filter (best-effort; only drop if we know the district).
    if cfg.districts and lst.district:
        if not any(d.lower() == lst.district.lower() for d in cfg.districts):
            return False

    return True


def apply(listings: list[Listing], cfg) -> list[Listing]:
    kept = [l for l in listings if _keep(l, cfg)]
    log.info("Filters: %d -> %d listings", len(listings), len(kept))
    return kept
