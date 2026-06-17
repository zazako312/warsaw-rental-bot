# 🏠 Warsaw Rental Telegram Bot

An always-on Telegram bot that watches **OLX.pl** and **Otodom.pl** for new
apartment rentals in Warsaw and pushes each new match to you as a rich card —
photo album + price, floor, deposit, czynsz, amenities and availability date.

You pick your filters **right inside Telegram** with tap-to-toggle buttons
(neighborhoods, price, rooms, area, pets). No files to edit.

---

## What a listing looks like

A photo album, then:

> 🏠 **2-кімнатна 39м² за 2900zł**
> 📍 Warszawa, Wola
> Власник · Поверх: 6
> ▪️ Є паркінг
> ▪️ Тварини: дозволені
> ▪️ Є комірка
> ▪️ Депозит: 4 000 zł
> ▪️ Орендна плата (чинш): 780 zł
> ▪️ Доступно з 17 Червня
> 🔗 via OLX · 74 zł/m²

## The filter menu

Send `/filters` any time:

```
⚙️ Налаштування пошуку
🏙 Райони · 💰 Ціна · 🚪 Кімнати · 📐 Площа
🐾 Тварини: ✅   ⏸ Пауза   🔄 Перевірити зараз
```

Tap **🏙 Райони** → toggle districts (✅ = active). Tap **💰 Ціна** → pick a
price ceiling. **🔄 Перевірити зараз** checks immediately. **⏸ Пауза** stops
alerts without losing your settings. Every change saves instantly.

---

## Setup

### 1. Create the bot + get your chat ID

1. In Telegram open **@BotFather** → `/newbot` → copy the **token**
   (`123456789:AAH...`). Open your new bot and tap **Start**.
2. Open **@userinfobot** → tap Start → copy your numeric **Id**.

### 2. Deploy on GitHub Actions (free forever, no credit card)

This runs in the cloud on a schedule — no server, no card. The only requirement
for unlimited free minutes is a **public** repository (your token is NOT in the
code; it lives in encrypted repo secrets).

1. Create a **new public repository** on GitHub.
2. Upload all files in this folder (drag-and-drop, or `git push`), keeping the
   folder structure.
3. **Settings → Secrets and variables → Actions → New repository secret**, add:
   - `TELEGRAM_BOT_TOKEN` → the token from step 1
   - `TELEGRAM_CHAT_ID` → your id
4. **Settings → Actions → General → Workflow permissions** → select
   **Read and write permissions** → Save. (Lets it remember what it already sent.)
5. Open the **Actions** tab, enable workflows, open **poll-rentals** →
   **Run workflow** → tick **Prime mode** → Run. This records current listings
   silently so you aren't flooded.
6. Done. It now runs every 15 minutes automatically.

**Using the filter menu:** in Telegram send `/start`, then `/filters`, and tap
to set neighborhoods/price/etc. Because this is a scheduled host, your taps are
applied on the **next run** (within ~15 min) rather than instantly — the menu
message updates itself once processed. To change how often it runs, edit the
`cron:` line in `.github/workflows/poll.yml` (e.g. `*/5 * * * *` for every 5 min).

> Prefer an **instant** menu? Run it on your own computer instead:
> ```bash
> pip install -r requirements.txt
> export TELEGRAM_BOT_TOKEN=xxxx TELEGRAM_CHAT_ID=yyyy
> python -m bot.app
> ```
> Real-time menu, free, no card — but only runs while your computer is on.

---

## Default filters (change them in the menu any time)

2 000–4 500 zł · 1–3 rooms · ≥28 m² · central districts (Śródmieście, Wola,
Mokotów, Ochota, Praga-Południe, Żoliborz) · short-term/scam listings filtered
out. `config.yaml` only sets these *initial defaults* — once the bot runs, your
menu choices live in `filters.json`.

---

## How it works

```
filter menu (Telegram buttons) ─┐
                                 ├─ filters.json ─► each run (every 15 min)
OLX html  ─┐                     │                     │
Otodom json ┘─► scrape ──► filter ──► dedup (seen.json) ──► enrich detail page
                                                              │
                                              photo album + caption ─► you
```

- **OLX**: full HTML, parsed with BeautifulSoup, sorted newest-first, per district.
- **Otodom**: the JSON embedded in its `__NEXT_DATA__` script tag.
- **Enrichment**: each new listing's detail page is opened to pull floor,
  deposit, czynsz, amenities, photos and owner-vs-agency.
- **Dedup**: `seen.json` remembers what's been sent; OLX also surfaces some
  Otodom offers, and those are de-duplicated so you never see a flat twice.

Run the offline tests: `python tests/test_logic.py`.

---

## Two ways to run (both free, both already wired up)

- **GitHub Actions (default above)** — `python -m bot.cron`, scheduled in
  `.github/workflows/poll.yml`. Free forever on a public repo, button menu works
  with a short delay.
- **Always-on process** — `python -m bot.app` on your own computer / any host
  with a card-free plan. Instant button menu. (`Dockerfile` + `Procfile`
  included for container hosts.)

---

## Notes

- This is for personal apartment hunting. The 15-minute interval is deliberately
  gentle on both sites — please don't crank it down to seconds.
- Sites change their markup occasionally. Each scraper logs how many listings it
  collected and is isolated, so if one source hiccups the other keeps working.
- Language of the cards/menu is Ukrainian (matching the requested style); it's
  all in `bot/notifier.py` and `bot/app.py` if you ever want to switch it.
