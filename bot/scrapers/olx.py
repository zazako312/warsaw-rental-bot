"""OLX.pl scraper for Warsaw apartment rentals.

OLX serves fully-rendered HTML, so we parse the listing cards directly.
URLs are built from the user's config (price / area / rooms / district),
sorted newest-first so the freshest offers come through.
"""
from __future__ import annotations

import re
import logging
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..http import get
from ..models import Listing

log = logging.getLogger("bot.olx")

BASE = "https://www.olx.pl/nieruchomosci/mieszkania/wynajem/warszawa/"
ROOM_ENUM = {1: "one", 2: "two", 3: "three", 4: "four"}

_ID_RE = re.compile(r"ID([0-9A-Za-z]+)\.html")
_PRICE_RE = re.compile(r"(\d[\d\s ]*)\s*zł")
_AREA_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*m²")


def _build_urls(cfg) -> list[str]:
    """One URL per district (OLX takes a single district_id per query)."""
    common = {"search[order]": "created_at:desc"}
    if cfg.price_min:
        common["search[filter_float_price:from]"] = cfg.price_min
    if cfg.price_max:
        common["search[filter_float_price:to]"] = cfg.price_max
    if cfg.area_min:
        common["search[filter_float_m:from]"] = int(cfg.area_min)
    for i, r in enumerate(cfg.rooms):
        if r in ROOM_ENUM:
            common[f"search[filter_enum_rooms][{i}]"] = ROOM_ENUM[r]

    district_ids = cfg.district_ids()
    if not district_ids:
        return [f"{BASE}?{urlencode(common)}"]

    urls = []
    for did in district_ids:
        params = dict(common)
        params["search[district_id]"] = did
        urls.append(f"{BASE}?{urlencode(params)}")
    return urls


def _parse_int_price(text: str):
    m = _PRICE_RE.search(text)
    if not m:
        return None
    digits = re.sub(r"[^\d]", "", m.group(1))
    return int(digits) if digits else None


def _parse_area(text: str):
    m = _AREA_RE.search(text)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _parse_cards(html: str) -> list[Listing]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select('[data-cy="l-card"]') or soup.select('[data-testid="l-card"]')
    listings: list[Listing] = []

    for card in cards:
        link = card.find("a", href=True)
        if not link:
            continue
        href = link["href"]
        if href.startswith("/"):
            href = "https://www.olx.pl" + href

        m = _ID_RE.search(href)
        listing_id = m.group(1) if m else (card.get("id") or href)

        # Otodom offers are also surfaced inside OLX results; tag the source
        # by the destination domain so dedup works across both scrapers.
        source = "otodom" if "otodom.pl" in href else "olx"

        title_el = card.find(["h4", "h6"]) or link
        title = title_el.get_text(strip=True) if title_el else "(no title)"

        text = card.get_text(" ", strip=True)
        price = _parse_int_price(text)
        area = _parse_area(text)

        district = None
        loc = card.select_one('[data-testid="location-date"]')
        if loc:
            loc_txt = loc.get_text(" ", strip=True)
            # Format: "Warszawa, Mokotów - Dzisiaj o 10:18"
            mloc = re.search(r"Warszawa,\s*([^\-–]+)", loc_txt)
            if mloc:
                district = mloc.group(1).strip()

        img_el = card.find("img")
        image = img_el.get("src") if img_el else None
        if image and "no_thumbnail" in image:
            image = None

        listings.append(Listing(
            source=source, listing_id=str(listing_id), title=title, url=href,
            price=price, area=area, district=district, image=image,
        ))
    return listings


def scrape(cfg, session) -> list[Listing]:
    all_listings: dict[str, Listing] = {}
    for url in _build_urls(cfg):
        html = get(session, url)
        if not html:
            log.error("OLX: no response for %s", url)
            continue
        try:
            for lst in _parse_cards(html):
                all_listings[lst.key] = lst
        except Exception:  # noqa: BLE001 - never let one page kill the run
            log.exception("OLX: failed to parse %s", url)
    log.info("OLX: collected %d listings", len(all_listings))
    return list(all_listings.values())
