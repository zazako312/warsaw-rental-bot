"""Offline tests for parsing/filtering/formatting logic (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bot.config import Config
from bot.models import Listing
from bot.filters import apply as apply_filters
from bot.scrapers.olx import _parse_cards, _build_urls
from bot.scrapers.otodom import _extract_next_data, _find_items, _to_listing, _build_url
from bot.notifier import format_caption
from bot.details import _enrich_otodom, _enrich_olx

CFG = Config({
    "search": {"price_min": 2000, "price_max": 4500, "area_min": 28,
               "rooms": [1, 2, 3], "districts": ["Mokotów", "Wola"]},
    "filters": {"exclude_keywords": ["dziennie", "noclegi"], "price_sanity_min": 1200},
    "poll": {"max_per_cycle": 15},
})

OLX_HTML = """
<div data-cy="l-card" id="111">
  <a href="/d/oferta/super-flat-CID3-ID19RUkA.html">link</a>
  <h4>Wynajmę 2pokojowe mieszkanie na Mokotowie</h4>
  <p data-testid="ad-price">3 200 zł</p>
  <p data-testid="location-date">Warszawa, Mokotów - Dzisiaj o 10:18</p>
  <span>57 m²</span>
  <img src="https://img/x.jpg"/>
</div>
<div data-cy="l-card" id="222">
  <a href="https://www.otodom.pl/pl/oferta/nice-ID4At5E.html">link</a>
  <h4>2 pokoje Wola bez prowizji</h4>
  <p data-testid="ad-price">3 500 zł</p>
  <p data-testid="location-date">Warszawa, Wola - Dzisiaj o 15:45</p>
  <span>36,82 m²</span>
</div>
<div data-cy="l-card" id="333">
  <a href="/d/oferta/nocleg-CID3-ID000.html">link</a>
  <h4>Mieszkanie na doby / noclegi</h4>
  <p data-testid="ad-price">150 zł</p>
  <p data-testid="location-date">Warszawa, Mokotów - Dzisiaj</p>
  <span>30 m²</span>
</div>
"""

OTODOM_HTML = """
<html><body>
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"data":{"searchAds":{"items":[
 {"id":987654,"slug":"mieszkanie-mokotow-abc","title":"Jasne 2 pokoje Mokotów",
  "totalPrice":{"value":3400,"currency":"PLN"},"areaInSquareMeters":42,
  "roomsNumber":"TWO","location":{"address":{"district":{"name":"Mokotów"}}},
  "images":[{"medium":"https://img/m.jpg"}]}
]}}}}}
</script>
</body></html>
"""


def test_olx_parse_and_filter():
    listings = _parse_cards(OLX_HTML)
    assert len(listings) == 3
    by_id = {l.listing_id: l for l in listings}
    assert by_id["19RUkA"].price == 3200
    assert by_id["19RUkA"].area == 57.0
    assert by_id["19RUkA"].district == "Mokotów"
    assert by_id["19RUkA"].source == "olx"
    assert by_id["4At5E"].source == "otodom"     # otodom link inside OLX results
    assert by_id["4At5E"].area == 36.82

    kept = apply_filters(listings, CFG)
    titles = {l.title for l in kept}
    assert "Mieszkanie na doby / noclegi" not in titles   # keyword + cheap dropped
    assert len(kept) == 2


def test_otodom_parse():
    data = _extract_next_data(OTODOM_HTML)
    items = _find_items(data)
    assert len(items) == 1
    lst = _to_listing(items[0])
    assert lst.source == "otodom"
    assert lst.listing_id == "987654"
    assert lst.price == 3400
    assert lst.rooms == 2
    assert lst.district == "Mokotów"
    assert lst.url.endswith("mieszkanie-mokotow-abc")


def test_url_building():
    olx_urls = _build_urls(CFG)
    assert len(olx_urls) == 2  # one per district
    assert "filter_float_price%3Ato" in olx_urls[0] or "filter_float_price:to" in olx_urls[0]
    ot_url = _build_url(CFG)
    assert "priceMax=4500" in ot_url
    assert "mokotow" in ot_url


def test_message_format():
    lst = Listing(source="olx", listing_id="x", title="Test & <flat>",
                  url="https://x/y", price=2900, area=39.0, rooms=2, district="Wola",
                  floor="6", deposit=4000, admin_rent=780, is_private=True,
                  parking=True, pets=True, storage=True, balcony=True, elevator=True,
                  available_from="17 Червня")
    msg = format_caption(lst)
    assert "&amp;" in msg and "&lt;flat&gt;" in msg          # html-escaped
    assert "2-кімнатна 39м² за 2900zł" in msg
    assert "📍 <b>Warszawa, Wola</b>" in msg
    assert "Власник" in msg and "Поверх: 6" in msg
    assert "Депозит: 4 000 zł" in msg
    assert "Орендна плата (чинш): 780 zł" in msg
    assert "Доступно з 17 Червня" in msg
    assert "Є паркінг" in msg and "Тварини: дозволені" in msg


OTODOM_DETAIL = """
<script id="__NEXT_DATA__" type="application/json">
{"props":{"pageProps":{"ad":{
  "description":"<p>Mieszkanie z balkonem, winda, miejsce parkingowe, piwnica.</p>",
  "advertiserType":"PRIVATE",
  "images":[{"large":"https://img/1-l.jpg"},{"large":"https://img/2-l.jpg"}],
  "target":{"Deposit":["4000"],"Rent":["780"],"Floor_no":["floor_6"]}
}}}}
</script>
"""


def test_otodom_enrich():
    lst = Listing(source="otodom", listing_id="1", title="t", url="https://o/1")
    _enrich_otodom(lst, OTODOM_DETAIL)
    assert lst.deposit == 4000
    assert lst.admin_rent == 780
    assert lst.floor == "6"
    assert lst.is_private is True
    assert lst.images == ["https://img/1-l.jpg", "https://img/2-l.jpg"]
    assert lst.balcony and lst.elevator and lst.parking and lst.storage


OLX_DETAIL = """
<html><body>
<div data-cy="ad_description">Mieszkanie umeblowane, z balkonem i windą. Można z tw.</div>
<ul><li>Kaucja: 4 000 zł</li><li>Czynsz (dodatkowo): 780 zł</li>
<li>Poziom: 6</li><li>Oferta od: Osoby prywatnej</li>
<li>Dostępne od: 17.06.2026</li></ul>
<img src="https://ireland.apollo.olxcdn.com/v1/files/abc-PL/image;s=216x152"/>
</body></html>
"""


def test_olx_enrich():
    lst = Listing(source="olx", listing_id="1", title="t", url="https://x/1")
    _enrich_olx(lst, OLX_DETAIL)
    assert lst.deposit == 4000
    assert lst.admin_rent == 780
    assert lst.floor == "6"
    assert lst.is_private is True
    assert lst.furnished and lst.balcony and lst.elevator
    assert lst.images and "1000x700" in lst.images[0]


def test_settings_and_menus(tmp_state="/tmp/filters_test.json"):
    import os
    os.environ["STATE_DIR"] = "/tmp"
    # reload modules so STATE picks up the env var
    import importlib, bot.settings as bs
    importlib.reload(bs)
    if os.path.exists(bs.STATE):
        os.remove(bs.STATE)

    s = bs.Settings()
    n0 = len(s.districts)
    s.toggle_district("Bemowo")
    assert "Bemowo" in s.districts and len(s.districts) == n0 + 1
    s.toggle_district("Bemowo")
    assert "Bemowo" not in s.districts
    s.toggle_room(4)
    assert 4 in s.rooms
    s.set_field("price_max", 5000)
    assert s.price_max == 5000

    # persistence round-trip
    s2 = bs.Settings()
    assert s2.price_max == 5000 and 4 in s2.rooms

    from bot.app import main_menu, dist_menu, price_menu, rooms_menu, area_menu
    for fn in (main_menu, dist_menu, price_menu, rooms_menu, area_menu):
        text, kb = fn(s)
        assert isinstance(text, str) and text
        assert isinstance(kb, list) and all(isinstance(r, list) for r in kb)
    # callback_data must stay within Telegram's 64-byte limit
    for fn in (main_menu, dist_menu, price_menu, rooms_menu, area_menu):
        _, kb = fn(s)
        for row in kb:
            for b in row:
                assert len(b["callback_data"].encode("utf-8")) <= 64, b


if __name__ == "__main__":
    test_olx_parse_and_filter()
    test_otodom_parse()
    test_url_building()
    test_message_format()
    test_otodom_enrich()
    test_olx_enrich()
    test_settings_and_menus()
    print("ALL TESTS PASSED")
