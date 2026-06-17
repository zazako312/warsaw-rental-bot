"""Persistent record of already-seen listings, so we only alert once."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("bot.store")

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = Path(os.environ.get("STATE_DIR", ROOT))
DEFAULT_PATH = STATE_DIR / "seen.json"
MAX_KEEP = 6000  # bound the file size; oldest keys drop off


class SeenStore:
    def __init__(self, path: Path | str | None = None):
        self.path = Path(path) if path else DEFAULT_PATH
        self._order: list[str] = []
        self._set: set[str] = set()
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._order = list(data.get("ids", []))
                self._set = set(self._order)
            except Exception:  # noqa: BLE001
                log.warning("Could not read %s; starting fresh", self.path)

    def has(self, key: str) -> bool:
        return key in self._set

    def has_any(self) -> bool:
        return bool(self._order)

    def add(self, key: str):
        if key not in self._set:
            self._set.add(key)
            self._order.append(key)

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if len(self._order) > MAX_KEEP:
            self._order = self._order[-MAX_KEEP:]
            self._set = set(self._order)
        self.path.write_text(
            json.dumps({"ids": self._order}, ensure_ascii=False),
            encoding="utf-8",
        )
        log.info("Saved %d seen ids to %s", len(self._order), self.path)
