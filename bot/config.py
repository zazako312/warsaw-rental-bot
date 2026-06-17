"""Load configuration from config.yaml + environment variables."""
from __future__ import annotations

import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.yaml"

# Warsaw district name -> OLX district_id (used to build OLX URLs).
OLX_DISTRICTS = {
    "Mokotów": 353, "Wola": 359, "Śródmieście": 351, "Praga-Południe": 381,
    "Białołęka": 365, "Bemowo": 367, "Ochota": 355, "Ursynów": 373,
    "Włochy": 357, "Praga-Północ": 379, "Bielany": 369, "Ursus": 371,
    "Targówek": 377, "Żoliborz": 363, "Wilanów": 375, "Wawer": 383,
    "Rembertów": 361, "Wesoła": 533,
}


class Config:
    def __init__(self, data: dict):
        s = data.get("search", {})
        f = data.get("filters", {})
        p = data.get("poll", {})

        self.price_min = int(s.get("price_min", 0) or 0)
        self.price_max = int(s.get("price_max", 0) or 0)
        self.area_min = float(s.get("area_min", 0) or 0)
        self.rooms = [int(r) for r in (s.get("rooms") or [])]
        self.districts = [d.strip() for d in (s.get("districts") or []) if d.strip()]

        self.exclude_keywords = [k.lower() for k in (f.get("exclude_keywords") or [])]
        self.price_sanity_min = int(f.get("price_sanity_min", 0) or 0)

        self.interval_minutes = int(p.get("interval_minutes", 30) or 30)
        self.max_per_cycle = int(p.get("max_per_cycle", 15) or 15)

        # Secrets come from the environment, never the config file.
        self.telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    def district_ids(self):
        return [OLX_DISTRICTS[d] for d in self.districts if d in OLX_DISTRICTS]

    def validate_secrets(self):
        missing = []
        if not self.telegram_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        if missing:
            raise SystemExit(
                "Missing required environment variable(s): " + ", ".join(missing)
            )


def load_config(path: Path | str | None = None) -> Config:
    path = Path(path) if path else DEFAULT_CONFIG
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return Config(data)
