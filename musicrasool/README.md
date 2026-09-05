# 🎧 MusicRasool — Telegram Music & Video Streaming Bot

A production-ready, fully bilingual (فارسی 🇮🇷 / English 🇺🇸) Telegram bot that streams
**music** and **video** into group voice chats, with panels, inline keyboards, a queue /
playlist system, admin controls, per-group paid credits, TV & satellite channel streaming,
and a **helper userbot** account that joins the voice chats and does the actual streaming.

This project is a complete rebuild of the original
[`new2rasool/musicrasool`](https://github.com/new2rasool/musicrasool) repository.
The original source was **not runnable** (broken DB schema, invalid PyTgCalls usage,
broken cron jobs, missing bot token, deprecated `pyromod` dependency, duplicated
handlers, dead Melobit endpoints, …). Every feature, button, panel and UI flow of the
original has been preserved — and everything now actually works.

---

## ✨ Features

### 🎵 Music
- `پخش` / `Play` — play a replied audio/voice in the voice chat
- `پخش @user` / `Play @user` — play an audio **dedicated** to a user
- `پخش لینک` / `PlayLink` — play from a direct audio URL
- `پخش فایل` / `PlayFile` — play a **local file** on the server
- `سرچ` / `Search` — search & send a song (Melobit)
- `پخش خودکار` / `AutoPlay` — search & play a song automatically
- `مکث` / `Pause` · `ازسرگیری` / `Resume` · `توقف پخش` / `StopMusic`
- `صدای موزیک` / `MusicSound` — volume (1–200)
- Now-playing card with control buttons (pause / stop / resume / mute / unmute / close)

### 🎬 Video
- `پخش ویدیو` / `PlayVideo` — play a replied video (with its resolution)
- `پخش ویدیو @user` — dedicate a video
- `پخش لینک ویدیو` / `PlayLinkVideo` — play from a video URL (downloaded first,
  any container — the real resolution is probed before streaming)
- `پخش یوتیوب` / `YoutubePlay` — play a YouTube link (`watch`, `youtu.be`,
  `shorts`, `live`, `music.youtube`); downloaded with yt-dlp at ≤720p
- `سرچ یوتیوب` / `YoutubeSearch` — search YouTube and play the result
- `توقف ویدیو` / `StopVideo` · `صدای ویدیو` / `VideoSound`

### ⌨️ Slash commands (also accepted)
`/play` (reply / URL / username) · `/playvideo` · `/pause` · `/resume` · `/stop` ·
`/skip` (advances the playlist, or stops the current stream) · `/stopmusic` ·
`/stopvideo` · `/playlist` · `/stoplist` · `/playfile <path>`

### 🔁 Auto-reconnect & stable playback
A background watchdog (`tasks.watch_streams`) monitors every actively-playing
stream; if a voice chat drops unexpectedly (closed, network loss, kicked) it
**re-joins automatically** with the same media. Intentional stops never trigger
a reconnect, and streams are given up after a few failed attempts to avoid loops.

Playback is protected against the classic "music stops after a few seconds"
failure: a stale stream-end event from the *previous* song (fired by
`leave_group_call` internally) can no longer kill the *next* song
(ignore-window + per-stream generation counter), and a stream that ends
**too early** (partial download, ffmpeg hiccup, network blip) is **auto-retried
twice** before the bot leaves the call. During playlist playback the event
handler never touches the voice chat.

### 💾 Large & long media
- Downloads preserve the original file extension, verify the result is a
  non-empty file and **retry once** on partial/failed downloads.
- A "در حال دانلود ..." status message is shown while large files download.
- The media duration is recorded (from Telegram metadata / ffprobe) so the
  early-end detector never mistakes a legitimately long song for a failure.
- Long files are streamed directly from disk by ffmpeg/ntgcalls - streaming
  itself has no size limit (server disk space is the only constraint).
  Sending a file as a Telegram *message* is a different matter: Telegram caps
  bot uploads at 50 MB (and remote URLs at 20 MB), which is why `سرچ` and
  `پخش خودکار` download the track first and then upload the local file.
- For local files `پخش فایل`/`PlayFile` auto-detects audio vs video and the
  video resolution (ffprobe).

### 📺 TV & Satellite (پخش تیوی / PlayTv)
- Iranian national channels: شبکه ۱، ۲، ۳، ۵، خبر، آی‌فیلم، نمایش، نسیم، تماشا، ورزش
- Satellite channels: BBC, BBC Persian, Manoto, AvaFamily, AvaSeries, FarsiTv, PMC,
  PMC Royale, Vox 1/2, NavahangMusic, RadioJavan, Iran International, ITN, Gem* (9 channels),
  MBC Persia, Tapesh 1/2, Persiana, Oxir TV — all live HLS.

### 📋 Playlist system
- `افزودن به لیست` (reply to audio) — up to 10 songs per group
- `پخش لیست` · `توقف لیست` · `لیست پخش` · `حذف از لیست` · `پاکسازی لیست پخش`
  (background task, properly cancellable)

### 🛠 Admin & ownership
- Per-group paid credits (music & video separately): `تنظیم شارژ` / `آپدیت شارژ`,
  charge panel for 1/2/3/4 months, expiry reminders + auto-leave
- Music/video admins per group: `ترفیع موزیک`/`عزل موزیک`, `ترفیع ویدیو`/`عزل ویدیو`,
  `لیست مدیران`, `پیکربندی`, `پاکسازی مدیران` (reply + username/id forms)
- Group creators (مالک): `ترفیع مالک`/`عزل مالک`/`لیست مالکان`
- Global admins: `همگانی موزیک`/`همگانی ویدیو`
- Sudo system: `تنظیم سودو`/`حذف سودو`/`👥 لیست سودو های ربات`
- Owner/sudo private panel (full Persian layout preserved) — status, invoice, rates,
  broadcasts, force-join, group lists, install limits, auto-leave, channel settings…
- Force-join channel with exemptions: `معاف اجبار` / `تنظیم اجبار` / `لیست معافیت`
- `اعتبار` / `Credit`, `آیدی` / `Id`, `خروج` (leave), `حذف` (delete panel),
  `شروع ویس کال` / `StartVoiceCall`, `بن همگانی` / `BanAll`, `پینگ` / `Ping`, `ربات` / `Bot`

### 🤖 Helper userbot
- The **helper account** (a normal Telegram account) joins the group voice chats and
  streams the media through PyTgCalls.
- **First-run login through the bot**: in your private chat with the bot send `/login`,
  then enter the helper phone number and the login code (and 2FA password if enabled).
  The bot saves the session and you run `/restart` to activate streaming.
- `افزودن هلپر` button joins the helper into a group and promotes it.

### 🌍 Bilingual (FA / EN)
- Every command exists in Persian **and** English.
- Users switch their UI language anytime with `/language` (button on `/start`).
- Default language configurable via `DEFAULT_LANG`.

---

## 🧱 Architecture

```
musicrasool/
├── run.py / main.py        # entry points (app.run() – required by Pyrogram 2.x)
├── config.py               # .env loader + first-run console wizard
├── database.py             # thread-safe SQLite layer (all original tables)
├── i18n.py                 # bilingual helpers (fa/en) + language picker
├── utils.py                # access control, cards, keyboards, yt-dlp, Melobit
├── clients.py              # app (bot) + ubot (helper) + PyTgCalls + ntgcalls shim
├── convo.py                # conversation helper (replaces pyromod's c.ask)
├── tasks.py                # background tasks (credit expiry, info refresh)
├── handlers/
│   ├── private.py          # /start, /language, /restart, owner/sudo panel
│   ├── auth.py             # /login helper wizard (phone → code → 2FA)
│   ├── admin_panel.py      # owner/sudo reply-keyboard panel
│   ├── group_admin.py      # install/charge/credit/ban/admins/creators...
│   ├── playback.py         # play/pause/resume/stop/volume/playlists/search/yt
│   ├── tv.py               # playtv / stoptv
│   └── misc.py             # help/ping/bot/media-reply/easter eggs/new members
├── callbacks/
│   ├── router.py           # central callback dispatcher + access check
│   ├── panel.py            # install / charge / config / helper / delete panels
│   ├── player.py           # pause/stop/resume/mute/close buttons
│   ├── tv.py               # TV & satellite channel streaming
│   ├── help.py             # help sections (FA + EN)
│   └── events.py           # on_stream_end cleanup
├── assets/mersad.jpg|.mp4  # default now-playing card media (replaceable)
├── sessions/               # pyrogram sessions (bot + helper)
├── downloads/              # downloaded media
├── tests/                  # smoke + handler integration tests
└── install.sh / run.sh     # one-command install / run
```

**Libraries (single MTProto client — only Pyrogram):**

| Package | Version | Why |
|---|---|---|
| Python | 3.9 – 3.11 (recommended 3.10) | ntgcalls wheels |
| pyrogram | 2.0.106 | MTProto client (bot + helper) |
| py-tgcalls | 1.2.9 | classic `join_group_call` API (matches original bot) |
| ntgcalls | 1.1.3 | native WebRTC binding (prebuilt wheels) |
| yt-dlp | 2026.7.4 | YouTube download **and** search (`ytsearch`); the primary path for every YouTube command |
| youtube-search-python | 1.6.6 | optional fallback for YouTube search only |
| jdatetime | 6.0.1 | Jalali (Persian) timestamps |
| aiohttp / psutil / screeninfo / deprecation | pinned | py-tgcalls runtime deps |

> **Compatibility notes**
> - `py-tgcalls 1.2.9` uses the **classic** API (`join_group_call`,
>   `AudioPiped`/`AudioVideoPiped`, `on_stream_end`, `pause_stream`, …) — exactly what the
>   original bot expects. Do **not** "upgrade" to py-tgcalls 2.x, its API changed completely
>   (`play()`, `on_update`) and would require a rewrite.
> - `ntgcalls` **must stay on 1.1.x** (1.1.3). py-tgcalls 1.2.9 is built against the 1.1.x
>   bindings (`StreamStatus.Playing`, `InputMode.Shell`). `clients.py` contains a small shim
>   that also tolerates ntgcalls 1.2.x, but 1.1.3 is the tested pairing.
> - **Do not mix MTProto clients**: Pyrogram everywhere, no Telethon anywhere.
> - `pyromod` is **not** used (it is unmaintained and breaks Pyrogram 2.x); its `c.ask`
>   feature is replaced by `convo.py`.

---

## 🚀 Quick start (automatic)

### Linux / macOS
```bash
git clone https://github.com/new2rasool/musicrasool.git
cd musicrasool
chmod +x install.sh run.sh
./install.sh          # finds Python, installs FFmpeg, creates venv, installs
                      # pinned requirements, and asks for .env values
./run.sh              # or: source venv/bin/activate && python run.py
```

### Windows
```bat
cd musicrasool
install.bat           # creates venv, installs requirements (+ static ffmpeg if missing)
run.bat
```

The installer auto-detects a suitable Python (3.9–3.12), falls back to a static
`ffmpeg` (via `imageio-ffmpeg`) when no system ffmpeg is found, and — if `ntgcalls
1.1.3` has no prebuilt wheel for your Python — automatically tries `ntgcalls 1.2.3`
(the compat shim in `clients.py` supports both). On first run, if `.env` is
missing, an **interactive wizard** collects `API_ID / API_HASH / BOT_TOKEN /
OWNER_ID / SUDO_ID`.

See **`INSTALL.md`** for the full manual installation guide (system deps for
Ubuntu/Debian/CentOS/macOS/Windows, venv setup, `.env`, helper login).

---

## 🛠 Manual installation

### 1. System dependencies
```bash
# Debian / Ubuntu
sudo apt update && sudo apt install -y ffmpeg python3.10 python3.10-venv python3-pip git

# CentOS / Rocky / Alma
sudo dnf install -y epel-release ffmpeg python3-pip git

# macOS (Homebrew)
brew install ffmpeg python@3.10 git
```

### 2. Python environment
```bash
python3.10 -m venv venv
source venv/bin/activate
pip install --upgrade pip wheel setuptools
pip install -r requirements.txt
```

### 3. Configuration
```bash
cp .env.example .env
nano .env
```
- `API_ID` / `API_HASH` — from https://my.telegram.org
- `BOT_TOKEN` — from @BotFather
- `OWNER_ID` / `SUDO_ID` — your numeric Telegram id (get it from @userinfobot or by
  sending `/start` to the bot — both can be the same id)
- `DEFAULT_LANG` — `fa` or `en`

### 4. First run & helper login
```bash
python run.py
```
1. The bot starts and, in your private chat, reminds you that the **helper account**
   is not logged in.
2. Send `/login` to the bot in private.
3. Enter the helper **phone number** (international format, e.g. `+989123456789`).
4. Enter the **login code** sent to that phone/Telegram.
5. If 2FA is enabled, enter the password.
6. Send `/restart` — the bot restarts with the helper session active.

> The helper is the account that joins voice chats and streams. It must be added to
> each group where you want streaming (button **افزودن هلپر** in the group install
> panel, or just add it manually).

---

## 📖 Usage

### Private chat with the bot
| Command | Description |
|---|---|
| `/start` | welcome + owner/sudo panel + language button |
| `/language` | switch UI language (فارسی / English) |
| `/login` | helper account login wizard (owner) |
| `/restart` | restart the bot (owner) |
| `/cancel` | abort the current wizard |

### In groups (Persian / English)
| Persian | English | Slash | Action |
|---|---|---|---|
| `نصب` | `install` | — | open the install panel |
| `پخش` (reply) | `play` | `/play` | play replied audio (or URL / username) |
| `پخش @user` (reply) | `play @user` | `/play @user` | dedicated playback |
| `پخش ویدیو` (reply) | `playvideo` | `/playvideo` | play replied video |
| `پخش لینک` | `playlink` | — | play audio URL |
| `پخش لینک ویدیو` | `playlinkvideo` | — | play video URL |
| `پخش فایل` | `playfile` | `/playfile` | play a local file |
| `پخش یوتیوب` | `youtubeplay` | — | play YouTube link |
| `سرچ یوتیوب` | `youtubesearch` | — | search & play YouTube |
| `سرچ` | `search` | — | search & send song |
| `پخش خودکار` | `autoplay` | — | search & auto play |
| `مکث` / `ازسرگیری` | `pause` / `resume` | `/pause` `/resume` | pause / resume |
| `توقف پخش` / `توقف ویدیو` | `stopmusic` / `stopvideo` | `/stop` `/stopmusic` `/stopvideo` | stop |
| — | — | `/skip` | next playlist track / stop current |
| `صدای موزیک N` / `صدای ویدیو N` | `musicsound N` / `videosound N` | — | volume |
| `افزودن به لیست` (reply) | `addtoplaylist` | — | add to playlist |
| `پخش لیست` / `توقف لیست` | `playlist` / `stoplist` | `/playlist` `/stoplist` | playlist play/stop |
| `لیست پخش` / `پاکسازی لیست پخش` | `listplaylist` / `cleanplaylist` | — | list/clear |
| `پخش تیوی` / `توقف تیوی` | `playtv` / `stoptv` | — | TV panel / stop |
| `اعتبار` | `credit` | — | group credit |
| `آیدی` / `ایدی` | `id` | — | user info |
| `راهنما` | `help` | — | help panel |
| `پینگ` / `ربات` | `ping` / `bot` | — | online status |

Admin commands (see `/help` panel or `README` of the original): install/delete panels,
charge commands (`تنظیم شارژ [گروه] [روز]`, `آپدیت شارژ …`), promote/demote music &
video admins, creators, sudos, global admins, force-join exemptions, ban-all, broadcasts,
and the full owner/sudo reply-keyboard panel in private.

---

## 🧪 Testing

```bash
python tests/run_all.py        # runs the FULL suite
```

| Test | What it verifies |
|---|---|
| `tests/smoke_test.py` | full startup path (`main.main()`), 144 handlers register in 2 groups, clean shutdown — zero errors |
| `tests/test_handlers.py` | 31 end-to-end checks driving handlers/callbacks with fakes (charge/install DB writes, player access control, TV streaming, volume, `/play`, `/skip`, local-file playback, auto-reconnect watchdog) |
| `tests/test_auth.py` | 33 checks on the helper login wizard (phone → code → 2FA, wrong-code retry, `/cancel`, Pyrogram 2.x `sign_in` argument order, signature-adaptive `_do_sign_in`, and that the success message names the **helper**, not the bot) |
| `tests/test_layout.py` | 15 layout-parity checks: every panel/button row and its order matches the original GitHub source exactly |
| `tests/test_panel_buttons.py` | 42 dispatcher-level checks: every developer-panel button reaches its handler and produces a reply (regression for the "buttons do nothing" bug) |
| `tests/test_stream_lifecycle.py` | 9 checks: stale stream-end events are dropped, early ends are auto-retried, natural ends leave cleanly, playlists are untouched, watchdog is non-destructive, the installed `ntgcalls` status enum is mapped |
| `tests/test_regressions.py` | 49 checks pinning the fixes from `AUDIT.md`: force-join honours `channel.status`, `پینگ` reaches the helper ping, `backtv` edits in place, `helper_ready()` reflects the real start result, the expiry task advances `status` even when `get_chat` fails, `پاکسازی` keeps playlist files, `PromoteMusic` strips its command word, `بیصدا`/`باصدا` exist, `PlayFile` cannot escape `downloads/`, no shipped credentials |

Each test runs offline and must pass with **zero errors**:

```console
RESULT: 49/49 regression checks passed
ALL TESTS PASSED
```

> **The suite never writes to your project.** `tests/_bootstrap.py` redirects
> `.env`, `database.sqlite`, `sessions/` and `downloads/` into a temporary
> directory before any project module is imported, so running the tests on a
> live host can no longer replace your bot token or wipe your charge/install
> tables. (It used to — see `AUDIT.md`, finding C1.)

---

## ⚙️ Performance & stability notes

- Single asyncio event loop; SQLite access is lock-protected (no cross-thread cursor bugs).
- Media files are cleaned when playback stops/ends; `downloads/` can be purged with
  `پاکسازی`.
- Playlists run as cancellable background tasks (no blocking of other chats).
- Expiry/credit checks run as lightweight background loops (no broken aiocron).
- All Telegram API calls are wrapped with try/except and friendly messages.
- Multi-group support: independent per-chat state (`PLAYING`, `PLAYLIS`, playlist tasks).

---

## 🔐 Security notes

- Keep `.env` private (it contains your bot token and API credentials).
- The helper session (`sessions/helper.session`) gives full control of that account —
  use a dedicated account, never your main account.
- Only the configured owner/sudo can run `/login`, `/restart` and panel operations.

---

## 📦 Version compatibility matrix

| Component | Version | Notes |
|---|---|---|
| Python | 3.9 – 3.11 | 3.10 recommended; ntgcalls wheels |
| pyrogram | 2.0.106 | handler registration requires `app.run()` (implemented) |
| py-tgcalls | 1.2.9 | classic API — do not upgrade to 2.x |
| ntgcalls | 1.1.3 | native binding; shim tolerates 1.2.x |
| yt-dlp | 2026.7.4 | direct stream extraction |
| youtube-search-python | 1.6.6 | provides `youtubesearchpython.VideosSearch` |
| FFmpeg | 4.x – 7.x | system package (or imageio-ffmpeg static binary) |

## ❓ Troubleshooting

- **`No module named ntgcalls` / build errors** — you are on Python 3.12+ without wheels:
  use Python 3.9–3.11 (ntgcalls 1.1.3 ships wheels up to cp312).
- **Bot starts but doesn't react** — you launched with `asyncio.run`; use `python run.py`
  (which uses `app.run()`).
- **Streaming says helper not logged in** — run `/login` then `/restart`.
- **"The bot is not an admin"** — promote the bot (and the helper) to admin in the group/channel.
- **YouTube fails** — make sure `yt-dlp` is installed and FFmpeg is on `PATH`.
- **Melobit search empty** — the public API may be rate-limited; retry later.

---

**Original repo:** https://github.com/new2rasool/musicrasool — this rebuild keeps every
panel, button and text of the original (Persian), and adds full English support, a working
helper-login flow, a stable stack and automated tests.
