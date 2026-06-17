# 📖 Easy setup guide (no tech experience needed)

Follow these in order. Take your time — it's about 15–20 minutes total, and you
only do it once. Nothing here can break your computer.

Words you'll see:
- **Bot** = your assistant inside Telegram.
- **Token** = a secret password for your bot.
- **GitHub** = a free website that will run your bot in the cloud, 24/7.
- **Repository (repo)** = just a folder of your files on GitHub.

---

## PART 1 — Create your Telegram bot (5 min)

1. Open **Telegram**. In the search bar, type **BotFather** and open the one
   with the blue checkmark.
2. Tap **Start**, then send this message:  `/newbot`
3. It asks for a **name** → type anything, e.g. `My Warsaw Flats`.
4. It asks for a **username** → must end in `bot`, e.g. `mk_warsaw_flats_bot`.
5. BotFather sends you a long code that looks like
   `123456789:AAH-xxxxxxxxxxxxxxxxxxxxx`.
   **This is your TOKEN. Copy it and keep it somewhere** (e.g. paste to yourself).
6. Now search for your new bot by its username, open it, and tap **Start**.
   (This step lets it message you.)

### Get your Chat ID
7. In Telegram search for **userinfobot**, open it, tap **Start**.
8. It replies with **Id: 123456789**. **Copy that number** — it's your CHAT ID.

✅ You now have two things saved: a **TOKEN** and a **CHAT ID**.

---

## PART 2 — Put the bot on GitHub (10 min)

### Make an account
1. Go to **github.com** and click **Sign up**. Make a free account
   (just email + password). No credit card, ever.

### Create the folder (repository)
2. After logging in, click the **+** in the top-right corner → **New repository**.
3. Repository name: type `warsaw-rental-bot`.
4. Choose **Public**. (This is what keeps it 100% free. Don't worry — your secret
   token is NOT stored in the files, you'll add it safely in Part 3.)
5. Click **Create repository**.

### Upload the files
6. Unzip the file I gave you (`warsaw-rental-bot.zip`). You'll get a folder.
7. On the new GitHub page, click the link **"uploading an existing file"**
   (it's in the middle of the page).
8. Open the unzipped folder on your computer. Select **everything inside it**
   (on Mac: `Cmd+A`, on Windows: `Ctrl+A`) and **drag it onto the GitHub page**.
9. Wait for the files to finish loading, then scroll down and click
   **Commit changes**.

> 💡 If you don't see a file/folder called `.github`, that's normal — it's
> hidden. Dragging everything still uploads it. (On Mac press `Cmd+Shift+.`
> to reveal hidden files if you want to check.)

---

## PART 3 — Add your secrets safely (3 min)

1. On your repository page, click **Settings** (top menu).
2. Left side: **Secrets and variables** → **Actions**.
3. Click **New repository secret**.
   - Name: `TELEGRAM_BOT_TOKEN`  → Secret: paste your **TOKEN** → **Add secret**.
4. Click **New repository secret** again.
   - Name: `TELEGRAM_CHAT_ID`  → Secret: paste your **CHAT ID** → **Add secret**.

### Allow it to save its memory
5. Still in **Settings**, left side click **Actions** → **General**.
6. Scroll down to **Workflow permissions**, choose
   **Read and write permissions**, and click **Save**.

---

## PART 4 — Turn it on (2 min)

1. Click the **Actions** tab (top menu). If it asks, click the green button to
   **enable workflows**.
2. On the left, click **poll-rentals**.
3. Click **Run workflow** (right side) → turn ON the **Prime mode** switch →
   click the green **Run workflow**.
   - This quietly learns which flats already exist so you don't get spammed.
4. Wait ~1 minute. Done! 🎉

From now on it checks OLX + Otodom every 15 minutes and sends you only **new**
flats.

---

## PART 5 — Use it & choose your filters

In Telegram, open your bot and send:  `/filters`

You'll see buttons:
- **🏙 Райони** — tap neighborhoods to turn them on/off (✅ = on)
- **💰 Ціна** — set your maximum rent
- **🚪 Кімнати** — number of rooms
- **📐 Площа** — minimum size
- **🐾 Тварини** — only flats that allow pets
- **⏸ Пауза** — stop alerts for a while
- **🔄 Перевірити зараз** — check right now

> One thing to know: because the bot runs every 15 minutes (to stay free),
> when you tap a button it updates on the **next** check — usually within
> 15 minutes. That's normal.

---

## If something seems off
- No messages at all? Make sure you tapped **Start** in your bot (Part 1, step 6),
  and that both secrets are spelled exactly `TELEGRAM_BOT_TOKEN` and
  `TELEGRAM_CHAT_ID`.
- Want to check it's running? **Actions** tab → you'll see green checkmarks for
  each run.
- Too many/few flats? Adjust price or neighborhoods with `/filters`.

That's it — happy flat hunting! 🏠
