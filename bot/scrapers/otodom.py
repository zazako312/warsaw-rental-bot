"""Otodom.pl scraper for Warsaw apartment rentals.

Otodom is a Next.js app: the search results are embedded as JSON inside a
<script id="__NEXT_DATA__"> tag in the initial HTML. We parse that JSON,
which is far more stable than scraping rendered DOM nodes.
"""
from __future__ import annotations

import json
import logging
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..http import get
from ..models import Listing

log = logging.getLogger("bot.otodom")

BASE = "https://www.otodom.pl/pl/wyniki/wynajem/mieszkanie/mazowieckie/warszawa/warszawa/warszawa"

# Otodom slugifies district names in the [DISTRICTS] query param.
DISTRICT_SLUG = {
    "Śródmieście": "srodmiescie", "Mokotów": "mokotow", "Wola": "wola",
    "Ochota": "ochota", "Praga-Południe": "praga-poludnie",
    "Praga-Północ": "praga-polnoc", "Żoliborz": "zoliborz",
    "Bielany": "bielany", "Bemowo": "bemowo", "Ursynów": "ursynow",
    "Włochy": "wlochy", "Ursus": "ursus", "Targówek": "targowek",
    "Wilanów": "wilanow", "Białołęka": "bialoleka", "Wawer": "wawer",
    "Rembertów": "rembertow", "Wesoła": "wesola",
}
ROOM_ENUM = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR"}


def _build_url(cfg) -> str:
    params = {"limit": 36, "by": "LATEST", "direction": "DESC", "viewType": "listing"}
    if cfg.price_min:
        params["priceMin"] = cfg.price_min
    if cfg.price_max:
        params["priceMax"] = cfg.price_max
    if cfg.area_min:
        params["areaMin"] = int(cfg.area_min)
    rooms = [ROOM_ENUM[r] for r in cfg.rooms if r in ROOM_ENUM]
    if rooms:
        params["roomsNumber"] = "[" + ",".join(rooms) + "]"
    slugs = [DISTRICT_SLUG[d] for d in cfg.districts if d in DISTRICT_SLUG]
    if slugs:
        params["locations"] = "[" + ",".join(
            f"districts_6-{s}" for s in slugs
        ) + "]"
    return f"{BASE}?{urlencode(params)}"


def _extract_next_data(html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        return json.loads(tag.string)
    except json.JSONDecodeError:
        log.exception("Otodom: could not decode __NEXT_DATA__")
        return None


def _find_items(data: dict) -> list[dict]:
    """Walk the JSON defensively to find the list of search-result ads."""
    try:
        return data["props"]["pageProps"]["data"]["searchAds"]["items"]
    except (KeyError, TypeError):
        pass

    # Fallback: recursively hunt for a list of dicts that look like ads.
    found: list[dict] = []

    def walk(node):
        if found:
            return
        if isinstance(node, dict):
            if "items" in node and isinstance(node["items"], list):
                items = node["items"]
                if items and isinstance(items[0], dict) and "slug" in items[0]:
                    found.extend(items)
                    return
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(data)
    return found


def _to_listing(item: dict) -> Listing | None:
    slug = item.get("slug")
    if not slug:
        return None
    listing_id = str(item.get("id") or slug)
    url = f"https://www.otodom.pl/pl/oferta/{slug}"
    title = item.get("title") or "(no title)"

    price = None
    tp = item.get("totalPrice") or item.get("rentPrice") or {}
    if isinstance(tp, dict):
        price = tp.get("value")
    elif isinstance(tp, (int, float)):
        price = tp
    if price is not None:
        price = int(price)

    area = item.get("areaInSquareMeters")
    if area is not None:
        area = float(area)

    rooms = item.get("roomsNumber")
    if isinstance(rooms, str):
        rooms = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4}.get(rooms.upper())

    district = None
    loc = item.get("location") or {}
    addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
    dist = addr.get("district") if isinstance(addr, dict) else None
    if isinstance(dist, dict):
        district = dist.get("name")

    image = None
    images = item.get("images") or []
    if images and isinstance(images[0], dict):
        image = images[0].get("medium") or images[0].get("large")

    return Listing(
        source="otodom", listing_id=listing_id, title=title, url=url,
        price=price, area=area, rooms=rooms, district=district, image=image,
    )


def scrape(cfg, session) -> list[Listing]:
    url = _build_url(cfg)
    html = get(session, url)
    if not html:
        log.error("Otodom: no response for %s", url)
        return []
    data = _extract_next_data(html)
    if not data:
        log.error("Otodom: __NEXT_DATA__ not found (page structure may have changed)")
        return []

    listings: dict[str, Listing] = {}
    for item in _find_items(data):
        try:
            lst = _to_listing(item)
            if lst:
                listings[lst.key] = lst
        except Exception:  # noqa: BLE001
            log.exception("Otodom: failed to parse an item")
    log.info("Otodom: collected %d listings", len(listings))
    return list(listings.values())
