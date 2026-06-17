"""Mutable user settings, edited live from the Telegram menu.

Seeded from config.yaml the first time, then persisted to filters.json.
Exposes the same attribute names the scrapers/filters expect, so it can be
used interchangeably with the static Config object.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path

from .config import OLX_DISTRICTS, load_config

log = logging.getLogger("bot.settings")

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.environ.get("STATE_DIR", ROOT))
STATE = STATE_DIR / "filters.json"

ALL_DISTRICTS = list(OLX_DISTRICTS.keys())
PRICE_MAX_PRESETS = [3000, 3500, 4000, 4500, 5000, 6000]
PRICE_MIN_PRESETS = [0, 2000, 2500, 3000]
AREA_PRESETS = [0, 25, 28, 30, 35, 40, 50]
ROOM_PRESETS = [1, 2, 3, 4]


class Settings:
    def __init__(self):
        self._lock = threading.RLock()
        base = load_config()  # defaults + static bits (keywords, interval, secrets)
        self.exclude_keywords = base.exclude_keywords
        self.price_sanity_min = base.price_sanity_min
        self.interval_minutes = base.interval_minutes
        self.max_per_cycle = base.max_per_cycle

        # user-editable
        self.price_min = base.price_min
        self.price_max = base.price_max
        self.area_min = base.area_min
        self.rooms = list(base.rooms)
        self.districts = list(base.districts)
        self.pets_only = False
        self.paused = False

        self._load()

    # ---- persistence ----
    def _load(self):
        if STATE.exists():
            try:
                d = json.loads(STATE.read_text(encoding="utf-8"))
                self.price_min = d.get("price_min", self.price_min)
                self.price_max = d.get("price_max", self.price_max)
                self.area_min = d.get("area_min", self.area_min)
                self.rooms = d.get("rooms", self.rooms)
                self.districts = d.get("districts", self.districts)
                self.pets_only = d.get("pets_only", self.pets_only)
                self.paused = d.get("paused", self.paused)
            except Exception:  # noqa: BLE001
                log.warning("Could not read %s; using defaults", STATE)

    def save(self):
        with self._lock:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            STATE.write_text(json.dumps({
                "price_min": self.price_min, "price_max": self.price_max,
                "area_min": self.area_min, "rooms": self.rooms,
                "districts": self.districts, "pets_only": self.pets_only,
                "paused": self.paused,
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- interface used by scrapers/filters ----
    def district_ids(self):
        return [OLX_DISTRICTS[d] for d in self.districts if d in OLX_DISTRICTS]

    # ---- mutators (thread-safe) ----
    def toggle_district(self, name):
        with self._lock:
            if name in self.districts:
                self.districts.remove(name)
            elif name in OLX_DISTRICTS:
                self.districts.append(name)
            self.save()

    def toggle_room(self, n):
        with self._lock:
            if n in self.rooms:
                self.rooms.remove(n)
            else:
                self.rooms.append(n)
            self.rooms.sort()
            self.save()

    def set_field(self, field, value):
        with self._lock:
            setattr(self, field, value)
            self.save()

    def toggle(self, field):
        with self._lock:
            setattr(self, field, not getattr(self, field))
            self.save()
