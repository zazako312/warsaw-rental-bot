"""Shared HTTP session with browser-like headers and polite retries."""
from __future__ import annotations

import time
import random
import logging

import requests

log = logging.getLogger("bot.http")

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
}


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def get(session: requests.Session, url: str, *, retries: int = 3, timeout: int = 30) -> str | None:
    """GET with simple retry/backoff. Returns response text or None on failure."""
    for attempt in range(1, retries + 1):
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200 and r.text:
                return r.text
            log.warning("GET %s -> HTTP %s (attempt %d)", url, r.status_code, attempt)
        except requests.RequestException as e:
            log.warning("GET %s failed: %s (attempt %d)", url, e, attempt)
        time.sleep(attempt * 2 + random.random())
    return None
