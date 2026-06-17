"""Interactive, always-on Telegram bot.

Serves a tap-to-toggle filter menu (neighborhoods, price, rooms, area, pets)
AND runs the apartment scraper on a schedule — all in one process.

Run it with:  python -m bot.app
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time

import requests

from .settings import (
    Settings, STATE_DIR, ALL_DISTRICTS, PRICE_MAX_PRESETS, PRICE_MIN_PRESETS,
    AREA_PRESETS, ROOM_PRESETS,
)
from .store import SeenStore
from .notifier import Telegram
from .engine import poll_cycle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bot.app")

API = "https://api.telegram.org/bot{token}/{method}"


# ───────────────────────── menu rendering ─────────────────────────
def _btn(text, data):
    return {"text": text, "callback_data": data}


def main_menu(s: Settings):
    dist = f"{len(s.districts)} obraní" if s.districts else "усі"
    price = f"{s.price_min or 0}–{s.price_max or '∞'} zł"
    rooms = ", ".join(map(str, s.rooms)) if s.rooms else "будь-яка"
    area = f"від {int(s.area_min)} m²" if s.area_min else "будь-яка"
    text = (
        "⚙️ <b>Налаштування пошуку</b>\n\n"
        f"🏙 Райони: <b>{dist}</b>\n"
        f"💰 Ціна: <b>{price}</b>\n"
        f"🚪 Кімнат: <b>{rooms}</b>\n"
        f"📐 Площа: <b>{area}</b>\n"
        f"🐾 Лише з тваринами: <b>{'так' if s.pets_only else 'ні'}</b>\n"
        f"🔔 Сповіщення: <b>{'⏸ на паузі' if s.paused else '▶️ увімкнені'}</b>"
    )
    kb = [
        [_btn("🏙 Райони", "m:dist"), _btn("💰 Ціна", "m:price")],
        [_btn("🚪 Кімнати", "m:rooms"), _btn("📐 Площа", "m:area")],
        [_btn(f"🐾 Тварини: {'✅' if s.pets_only else '—'}", "t:pets")],
        [_btn("⏸ Пауза" if not s.paused else "▶️ Увімкнути", "t:paused")],
        [_btn("🔄 Перевірити зараз", "act:check")],
    ]
    return text, kb


def dist_menu(s: Settings):
    rows, row = [], []
    for i, d in enumerate(ALL_DISTRICTS):
        mark = "✅ " if d in s.districts else ""
        row.append(_btn(f"{mark}{d}", f"d:{d}"))
        if len(row) == 2:
            rows.append(row); row = []
    if row:
        rows.append(row)
    rows.append([_btn("✓ Усі", "d:__all"), _btn("✗ Очистити", "d:__none")])
    rows.append([_btn("⬅️ Назад", "m:main")])
    return "🏙 <b>Райони Варшави</b>\nНатисніть, щоб увімкнути/вимкнути:", rows


def price_menu(s: Settings):
    maxrow = [_btn(f"{'• ' if s.price_max==v else ''}{v}", f"pmax:{v}") for v in PRICE_MAX_PRESETS]
    minrow = [_btn(f"{'• ' if s.price_min==v else ''}{v or 'будь-яка'}", f"pmin:{v}") for v in PRICE_MIN_PRESETS]
    rows = [maxrow[:3], maxrow[3:], minrow, [_btn("⬅️ Назад", "m:main")]]
    text = f"💰 <b>Ціна (zł/міс)</b>\nМакс: <b>{s.price_max or '∞'}</b> · Мін: <b>{s.price_min or 0}</b>"
    return text, rows


def rooms_menu(s: Settings):
    row = [_btn(f"{'✅ ' if n in s.rooms else ''}{n}", f"r:{n}") for n in ROOM_PRESETS]
    return "🚪 <b>Кількість кімнат</b>", [row, [_btn("⬅️ Назад", "m:main")]]


def area_menu(s: Settings):
    row = [_btn(f"{'• ' if int(s.area_min)==v else ''}{v or 'будь-яка'}", f"a:{v}") for v in AREA_PRESETS]
    rows = [row[:4], row[4:], [_btn("⬅️ Назад", "m:main")]]
    return f"📐 <b>Мінімальна площа</b>: {int(s.area_min) or 'будь-яка'} m²", rows


def render(view, s):
    return {"m:main": main_menu, "m:dist": dist_menu, "m:price": price_menu,
            "m:rooms": rooms_menu, "m:area": area_menu}.get(view, main_menu)(s)


# ───────────────────────── bot core ─────────────────────────
class InteractiveBot:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = str(chat_id)
        self.http = requests.Session()
        self.settings = Settings()
        self.store = SeenStore()
        self.notifier = Telegram(token, chat_id)
        self.check_now = threading.Event()
        self.offset_file = STATE_DIR / "tg_offset.json"

    # ---- update offset persistence (for one-shot / cron mode) ----
    def _load_offset(self):
        try:
            return json.loads(self.offset_file.read_text()).get("offset")
        except Exception:  # noqa: BLE001
            return None

    def _save_offset(self, offset):
        try:
            self.offset_file.parent.mkdir(parents=True, exist_ok=True)
            self.offset_file.write_text(json.dumps({"offset": offset}))
        except Exception:  # noqa: BLE001
            log.warning("Could not persist update offset")

    def api(self, method, **payload):
        try:
            r = self.http.post(API.format(token=self.token, method=method),
                               json=payload, timeout=40)
            return r.json() if r.ok else None
        except requests.RequestException as e:
            log.warning("API %s failed: %s", method, e)
            return None

    def show(self, chat_id, view, message_id=None):
        text, kb = render(view, self.settings)
        markup = {"inline_keyboard": kb}
        if message_id:
            self.api("editMessageText", chat_id=chat_id, message_id=message_id,
                     text=text, parse_mode="HTML", reply_markup=markup)
        else:
            self.api("sendMessage", chat_id=chat_id, text=text,
                     parse_mode="HTML", reply_markup=markup)

    # ---- update handlers ----
    def on_message(self, msg):
        chat_id = msg["chat"]["id"]
        text = (msg.get("text") or "").strip().lower()
        if text in ("/start", "/menu", "/filters", "/settings"):
            if text == "/start":
                self.api("sendMessage", chat_id=chat_id,
                         text="👋 Привіт! Я шукаю квартири у Варшаві на OLX та Otodom "
                              "і надсилаю нові оголошення сюди.\n\nОберіть фільтри нижче.")
            self.show(chat_id, "m:main")

    def on_callback(self, cq):
        data = cq.get("data", "")
        msg = cq.get("message", {})
        chat_id = msg.get("chat", {}).get("id")
        mid = msg.get("message_id")
        s = self.settings
        view = "m:main"
        toast = None

        if data.startswith("m:"):
            view = data
        elif data == "d:__all":
            s.set_field("districts", list(ALL_DISTRICTS)); view = "m:dist"
        elif data == "d:__none":
            s.set_field("districts", []); view = "m:dist"
        elif data.startswith("d:"):
            s.toggle_district(data[2:]); view = "m:dist"
        elif data.startswith("pmax:"):
            s.set_field("price_max", int(data[5:])); view = "m:price"
        elif data.startswith("pmin:"):
            s.set_field("price_min", int(data[5:])); view = "m:price"
        elif data.startswith("r:"):
            s.toggle_room(int(data[2:])); view = "m:rooms"
        elif data.startswith("a:"):
            s.set_field("area_min", float(data[2:])); view = "m:area"
        elif data == "t:pets":
            s.toggle("pets_only"); view = "m:main"
        elif data == "t:paused":
            s.toggle("paused"); view = "m:main"
        elif data == "act:check":
            self.check_now.set(); toast = "🔄 Перевіряю зараз…"; view = "m:main"

        self.api("answerCallbackQuery", callback_query_id=cq["id"],
                 **({"text": toast} if toast else {}))
        if chat_id and mid:
            self.show(chat_id, view, mid)

    # ---- loops ----
    def poll_updates(self):
        offset = None
        log.info("Listening for menu interactions…")
        while True:
            r = self.api("getUpdates", offset=offset, timeout=50)
            if not r or not r.get("ok"):
                time.sleep(3); continue
            for upd in r["result"]:
                offset = upd["update_id"] + 1
                try:
                    if "message" in upd:
                        self.on_message(upd["message"])
                    elif "callback_query" in upd:
                        self.on_callback(upd["callback_query"])
                except Exception:  # noqa: BLE001
                    log.exception("Failed handling update")

    def drain_updates(self, max_loops: int = 20):
        """Process all pending menu taps once, then return (cron mode)."""
        offset = self._load_offset()
        log.info("Draining pending menu interactions…")
        for _ in range(max_loops):
            r = self.api("getUpdates", offset=offset, timeout=0)
            if not r or not r.get("ok") or not r["result"]:
                break
            for upd in r["result"]:
                offset = upd["update_id"] + 1
                try:
                    if "message" in upd:
                        self.on_message(upd["message"])
                    elif "callback_query" in upd:
                        self.on_callback(upd["callback_query"])
                except Exception:  # noqa: BLE001
                    log.exception("Failed handling update")
        if offset is not None:
            self._save_offset(offset)

    def scrape_loop(self):
        log.info("Scraper loop started (every %d min)", self.settings.interval_minutes)
        # First ever launch: record what's already listed without spamming it.
        if not self.store.has_any():
            try:
                poll_cycle(self.settings, self.store, None, prime=True)
                self.notifier.send_text(
                    "✅ Бот запущено. Відстежую нові оголошення за вашими фільтрами. "
                    "Надішліть /filters, щоб змінити пошук."
                )
            except Exception:  # noqa: BLE001
                log.exception("Initial prime failed")
        while True:
            if not self.settings.paused:
                try:
                    poll_cycle(self.settings, self.store, self.notifier)
                except Exception:  # noqa: BLE001
                    log.exception("Scrape cycle failed")
            # Sleep, but wake early if the user tapped "Check now".
            self.check_now.wait(timeout=self.settings.interval_minutes * 60)
            self.check_now.clear()

    def run(self):
        threading.Thread(target=self.scrape_loop, daemon=True).start()
        self.poll_updates()


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.")
    InteractiveBot(token, chat_id).run()


if __name__ == "__main__":
    main()
