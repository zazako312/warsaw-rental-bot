"""Enrich a listing by reading its detail page (floor, deposit, czynsz,
amenities, owner/agency, all photos). Best-effort: anything we can't parse is
simply left blank, and the base card still goes out.
"""
from __future__ import annotations

import json
import re
import logging

from bs4 import BeautifulSoup

from .http import get
from .models import Listing

log = logging.getLogger("bot.details")

_NUM = lambda s: int(re.sub(r"[^\d]", "", s)) if s and re.search(r"\d", s) else None


# ───────────────────────── OLX ─────────────────────────
_OLX_IMG = re.compile(r"https://ireland\.apollo\.olxcdn\.com[^\s\"'\\]+")


def _yes(text: str, *needles: str) -> bool:
    t = text.lower()
    return any(n in t for n in needles)


def _enrich_olx(lst: Listing, html: str):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    # Photos (dedupe, biggest variant, keep order, max 10).
    seen, imgs = set(), []
    for m in _OLX_IMG.finditer(html):
        u = re.sub(r";s=\d+x\d+", ";s=1000x700", m.group(0))
        base = u.split(";")[0]
        if base not in seen:
            seen.add(base)
            imgs.append(u)
        if len(imgs) >= 10:
            break
    if imgs:
        lst.images = imgs

    desc_el = soup.select_one('[data-cy="ad_description"]') or soup.select_one('[data-testid="ad_description"]')
    if desc_el:
        lst.description = desc_el.get_text(" ", strip=True)

    def grab(label):
        # allow "(dodatkowo):" etc. between the label and the number
        m = re.search(label + r"\D{0,25}?([0-9][0-9\s\u00a0]*)\s*z\u0142", text, re.I)
        return _NUM(m.group(1)) if m else None

    lst.deposit = lst.deposit or grab(r"Kaucja")
    lst.admin_rent = lst.admin_rent or grab(r"Czynsz")

    mfloor = re.search(r"Poziom\s*:?\s*(parter|\d+)", text, re.I)
    if mfloor:
        lst.floor = mfloor.group(1)

    mavail = re.search(r"Dostępne od\s*:?\s*([0-3]?\d[\s.\-/][\w.]+)", text, re.I)
    if mavail:
        lst.available_from = mavail.group(1).strip()

    if "Osoby prywatnej" in text or "Prywatne" in text:
        lst.is_private = True
    elif "Biura" in text or "Deweloper" in text or "Firmy" in text:
        lst.is_private = False

    blob = (lst.description or "") + " " + text
    lst.furnished = _yes(text, "umeblowane: tak", "umeblowane tak") or _yes(blob, "umeblowan")
    lst.parking = _yes(blob, "parking", "garaż", "miejsce postojowe")
    lst.balcony = _yes(blob, "balkon", "taras")
    lst.elevator = _yes(blob, "winda", "windą", "windy", "lift")
    lst.storage = _yes(blob, "komórka", "komorka", "piwnica")
    lst.pets = True if _yes(blob, "zwierzęta dozwolone", "można z twierz", "można z tw", "zwierzaki ok", "pet friendly") else None


# ──────────────────────── Otodom ────────────────────────
def _otodom_ad(html: str) -> dict | None:
    soup = BeautifulSoup(html, "lxml")
    tag = soup.find("script", id="__NEXT_DATA__")
    if not tag or not tag.string:
        return None
    try:
        data = json.loads(tag.string)
    except json.JSONDecodeError:
        return None
    pp = (data.get("props") or {}).get("pageProps") or {}
    return pp.get("ad") or pp.get("adData") or None


def _enrich_otodom(lst: Listing, html: str):
    ad = _otodom_ad(html)
    if not ad:
        return

    images = []
    for im in (ad.get("images") or []):
        if isinstance(im, dict):
            images.append(im.get("large") or im.get("medium") or im.get("small"))
    images = [i for i in images if i][:10]
    if images:
        lst.images = images

    desc = ad.get("description")
    if isinstance(desc, str):
        lst.description = BeautifulSoup(desc, "lxml").get_text(" ", strip=True)

    target = ad.get("target") or {}

    def tnum(*keys):
        for k in keys:
            v = target.get(k)
            if isinstance(v, list) and v:
                v = v[0]
            if v not in (None, "", []):
                return _NUM(str(v))
        return None

    lst.deposit = lst.deposit or tnum("Deposit", "Deposit_value")
    lst.admin_rent = lst.admin_rent or tnum("Rent", "rent")
    fl = target.get("Floor_no")
    if isinstance(fl, list) and fl:
        fl = fl[0]
    if fl:
        lst.floor = str(fl).replace("floor_", "").replace("ground_floor", "parter")

    at = (ad.get("advertiserType") or target.get("advertiser_type") or "")
    if isinstance(at, str) and at:
        lst.is_private = at.upper() == "PRIVATE"

    feats = " ".join(str(x) for x in (
        (ad.get("featuresByCategory") or []) +
        (ad.get("features") or []) +
        list(target.values())
    )).lower()
    blob = feats + " " + (lst.description or "").lower()
    lst.furnished = _yes(blob, "umeblowan", "furnished", "wyposażon")
    lst.parking = _yes(blob, "parking", "garaż", "garage")
    lst.balcony = _yes(blob, "balkon", "balcony", "taras", "terrace")
    lst.elevator = _yes(blob, "winda", "lift", "elevator")
    lst.storage = _yes(blob, "komórka", "komorka", "piwnica", "basement", "utility")
    lst.pets = True if _yes(blob, "zwierzęta", "pets", "pet") else None


def enrich(lst: Listing, session) -> Listing:
    """Fetch + parse the detail page. Failures are swallowed (card still sends)."""
    try:
        html = get(session, lst.url, retries=2)
        if not html:
            return lst
        if lst.source == "otodom":
            _enrich_otodom(lst, html)
        else:
            _enrich_olx(lst, html)
    except Exception:  # noqa: BLE001
        log.exception("Enrich failed for %s", lst.url)
    return lst
