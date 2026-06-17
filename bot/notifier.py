"""Send rich listing cards to Telegram (photo album + Ukrainian caption)."""
from __future__ import annotations

import html
import logging
import time

import requests

from .models import Listing

log = logging.getLogger("bot.notifier")

API = "https://api.telegram.org/bot{token}/{method}"
CAPTION_LIMIT = 1024  # Telegram caption hard limit


def _fmt_price(v) -> str:
    return f"{v:,}".replace(",", " ")


def format_caption(lst: Listing) -> str:
    rooms = f"{lst.rooms}-кімнатна" if lst.rooms else "Квартира"
    area = f"{lst.area:g}м²" if lst.area else ""
    price = f"{lst.price}zł" if lst.price else "ціна не вказана"

    head = f'🏠 <b>{rooms} {area} за {price}</b>'.replace("  ", " ").strip()
    lines = [f'<a href="{html.escape(lst.url)}">{html.escape(lst.title)}</a>', "", head, ""]

    loc = "Warszawa"
    if lst.district:
        loc += f", {html.escape(lst.district)}"
    lines.append(f"📍 <b>{loc}</b>")
    lines.append("")

    if lst.is_private is True:
        lines.append("Власник")
    elif lst.is_private is False:
        lines.append("Агентство")
    if lst.floor:
        lines.append(f"Поверх: {html.escape(str(lst.floor))}")

    feats = []
    if lst.parking:
        feats.append("▪️ Є паркінг")
    if lst.pets:
        feats.append("▪️ Тварини: дозволені")
    if lst.storage:
        feats.append("▪️ Є комірка")
    if lst.furnished:
        feats.append("▪️ Меблі: так")
    if lst.balcony:
        feats.append("▪️ Балкон")
    if lst.elevator:
        feats.append("▪️ Ліфт")
    if lst.deposit:
        feats.append(f"▪️ Депозит: {_fmt_price(lst.deposit)} zł")
    if lst.admin_rent:
        feats.append(f"▪️ Орендна плата (чинш): {_fmt_price(lst.admin_rent)} zł")
    if lst.available_from:
        feats.append(f"▪️ Доступно з {html.escape(str(lst.available_from))}")
    ppm = lst.price_per_m2()
    if ppm:
        feats.append(f"▪️ {ppm:g} zł/m²")
    if feats:
        lines.append("")
        lines += feats

    lines.append("")
    lines.append(f"🔗 via {lst.source.upper()}")

    text = "\n".join(lines)
    if len(text) > CAPTION_LIMIT:
        text = text[: CAPTION_LIMIT - 1].rsplit("\n", 1)[0] + "…"
    return text


class Telegram:
    def __init__(self, token: str, chat_id: str):
        self.token = token
        self.chat_id = chat_id
        self.session = requests.Session()

    def _post(self, method: str, payload: dict) -> bool:
        url = API.format(token=self.token, method=method)
        try:
            r = self.session.post(url, json=payload, timeout=40)
            if r.status_code == 200:
                return True
            log.warning("Telegram %s -> %s: %s", method, r.status_code, r.text[:300])
        except requests.RequestException as e:
            log.warning("Telegram %s failed: %s", method, e)
        return False

    def send(self, lst: Listing) -> bool:
        caption = format_caption(lst)
        photos = lst.images or ([lst.image] if lst.image else [])
        photos = [p for p in photos if p][:10]

        # Album of 2-10 photos: caption rides on the first item.
        if len(photos) >= 2:
            media = []
            for i, url in enumerate(photos):
                item = {"type": "photo", "media": url}
                if i == 0:
                    item["caption"] = caption
                    item["parse_mode"] = "HTML"
                media.append(item)
            if self._post("sendMediaGroup", {"chat_id": self.chat_id, "media": media}):
                return True
            # fall through to single-photo / text on failure

        if len(photos) == 1:
            if self._post("sendPhoto", {
                "chat_id": self.chat_id, "photo": photos[0],
                "caption": caption, "parse_mode": "HTML",
            }):
                return True

        return self._post("sendMessage", {
            "chat_id": self.chat_id, "text": caption,
            "parse_mode": "HTML", "disable_web_page_preview": False,
        })

    def send_text(self, text: str) -> bool:
        return self._post("sendMessage", {
            "chat_id": self.chat_id, "text": text, "parse_mode": "HTML",
        })

    def broadcast(self, listings: list[Listing], pause: float = 2.0) -> int:
        sent = 0
        for lst in listings:
            if self.send(lst):
                sent += 1
            time.sleep(pause)  # media groups are rate-limited harder
        return sent
