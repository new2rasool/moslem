# ماژول ۲۴ — نصب و اجرا: خودکار و دستی (دوزبانه / Installation: FA + EN)

این سند دو روش نصب «ربات مدیریت گروه» را با توضیح فارسی و انگلیسی شرح می‌دهد:
**نصب خودکار** (یک‌دستور) و **نصب دستی** (قدم‌به‌قدم شفاف). در هر دو روش
خروجیِ نهایی یکی است: یک محیط `python` با وابستگی‌ها + فایل `.env` + پوشهٔ
`data/` برای دیتابیس و نشست Pyrogram.

> پیش‌نیاز / Prerequisites: **Python 3.10+** (`python3 --version`).
> در Ubuntu/Debian اگر `python3 -m venv` کار نکرد:
> `sudo apt install python3 python3-venv python3-pip`

---

## فارسی — نصب خودکار (یک دستور)

پس از استخراج سورس، از داخل پوشهٔ `group-manager-bot`:

```bash
./install.sh                 # نصب خودکار کامل (اجرا + توسعه: Pyrogram و pytest)
./install.sh --no-dev        # فقط وابستگی‌های اجرا (حجم کمتر؛ بدون pytest)
./install.sh --no-check      # اگر نمی‌خواهید بررسی سلامت اجرا شود
./install.sh --help          # راهنمای گزینه‌ها
```

`install.sh` به‌ترتیب این کارها را انجام می‌دهد:

1. **بررسی پایتون** — وجود Python 3.10+ را می‌سنجد.
2. **ساخت `.venv`** — یک محیط مجازی ایزوله در پوشهٔ پروژه می‌سازد.
3. **نصب پکیج** — `pip install -e ".[run,dev]"` (Pyrogram و TgCrypto برای
   اتصال واقعی + pytest برای تست)؛ با `--no-dev` فقط `-e ".[run]"` نصب می‌شود.
4. **ساخت `.env`** — اگر `.env` وجود نداشته باشد، از روی `.env.example` کپی
   می‌کند (مقادیر واقعی را خودتان باید وارد کنید؛ اگر `.env` موجود باشد دست
   نمی‌زند).
5. **ساخت `data/`** — پوشهٔ دیتابیس sqlite و نشست Pyrogram.
6. **بررسی سلامت** — `python -m bot.main --check` را اجرا می‌کند تا همهٔ
   پلاگین‌ها (۵۱ پلاگین / ۱۳۲ فرمان) بدون تلگرام بارگذاری شوند. خطای
   «OWNER_ID الزامی است» طبیعی است تا وقتی که `.env` را کامل نکرده‌اید.

سپس با یک دستور اجرا کنید:

```bash
./run.sh --run              # اجرای زنده
./run.sh --run --watch      # + هات‌ری‌لود خودکار پوشهٔ plugins
./run.sh --check            # بررسی سلامت هر زمان
```

`run.sh` فایل `.env` را خودکار بارگذاری می‌کند و ربات را با همان محیط اجرا
می‌کند — یعنی نیازی به `export` دستی نیست.

---

## English — Automatic install (one command)

From inside the `group-manager-bot` folder after extracting the source:

```bash
./install.sh                 # full automatic install (runtime + dev tools)
./install.sh --no-dev        # runtime dependencies only (smaller, no pytest)
./install.sh --no-check      # skip the final health check
./install.sh --help          # show options
```

`install.sh` performs, in order:

1. **Python check** — verifies Python 3.10+ is available.
2. **Create `.venv`** — an isolated virtualenv inside the project folder.
3. **Install the package** — `pip install -e ".[run,dev]"` (Pyrogram and
   TgCrypto for the real Telegram connection + pytest for the test suite);
   with `--no-dev` it installs only `-e ".[run]"`.
4. **Create `.env`** — copies `.env.example` if no `.env` exists yet (you must
   fill in the real values; an existing `.env` is kept untouched).
5. **Create `data/`** — folder for the sqlite database and the Pyrogram
   session.
6. **Health check** — runs `python -m bot.main --check` to load every plugin
   (51 plugins / 132 commands) without Telegram. The “OWNER_ID is required”
   error is expected until you finish editing `.env`.

Then run with a single command:

```bash
./run.sh --run              # live run
./run.sh --run --watch      # + auto hot-reload of the plugins folder
./run.sh --check            # health check anytime
```

`run.sh` loads `.env` for you and runs the bot with that environment — no
manual `export` needed.

---

## فارسی — نصب دستی (قدم‌به‌قدم)

اگر ترجیح می‌دهید همه‌چیز را خودتان کنترل کنید:

**قدم ۱ — ساخت محیط مجازی و نصب:**

```bash
cd group-manager-bot
python3 -m venv .venv
source .venv/bin/activate          # ویندوز: .venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[run,dev]"        # اجرا (Pyrogram) + تست (pytest) با هم
# فقط اجرا (بدون pytest):
# pip install -e ".[run]"
```

> نکته: اگر پکیج را با extras متفاوت دوباره نصب کنید، pip ممکن است
> وابستگی‌های قبلی را حذف کند؛ پس هر دو گروه را در **یک** دستور بیاورید
> (`".[run,dev]"`) یا از `./install.sh` استفاده کنید که خودش این کار را
> درست انجام می‌دهد.

> `-e` (editable) یعنی پکیج از همین پوشهٔ سورس اجرا می‌شود؛ پس پوشهٔ سورس را
> جابه‌جا/حذف نکنید و همیشه از داخل همان پوشه اجرا کنید تا `plugins/` و
> `data/` درست پیدا شوند.

**قدم ۲ — ساخت فایل پیکربندی `.env`:**

```bash
cp .env.example .env
nano .env        # یا هر ویرایشگر دیگر
```

حداقل این سه کلید را با مقادیر واقعی پر کنید:

| کلید | از کجا؟ | برای چه؟ |
|---|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` | احراز هویت ربات (اجباری) |
| `API_ID` | [my.telegram.org](https://my.telegram.org) → API development tools | اجرای زنده با Pyrogram |
| `API_HASH` | همان‌جا | اجرای زنده با Pyrogram |
| `OWNER_ID` | آیدی عددی شما (مثلاً با @userinfobot) | مالک/سودو — برای `--check` هم لازم است |

اختیاری: `SUDO_IDS=111,222` (سودوهای اضافه)، `GMB_DEFAULT_LANG=en|fa`
(زبان پیش‌فرض)، `GMB_DB_URL=sqlite:///data/…` (جای دیتابیس).

**قدم ۳ — بررسی سلامت (بدون تلگرام):**

```bash
python -m bot.main --check
```

خروجی موفق: «✅ هستهٔ پلاگین‌محور سالم است» + فهرست ۵۱ پلاگین.

**قدم ۴ — اجرای زنده:**

```bash
set -a; source .env; set +a        # بارگذاری متغیرها در همین شل
python -m bot.main --run           # اجرا
python -m bot.main --run --watch   # + هات‌ری‌لود پلاگین‌ها
```

یا بدون دست‌کاری export، از `./run.sh` استفاده کنید که خودش `.env` را
می‌خواند.

**قدم ۵ — تست‌ها (اختیاری):**

```bash
pip install -e ".[dev]"
python -m pytest -q                # انتظار: ۲۵۰ تست سبز
```

---

## English — Manual installation (step by step)

If you prefer full control:

**Step 1 — Create a virtualenv and install:**

```bash
cd group-manager-bot
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -e ".[run,dev]"        # runtime (Pyrogram) + tests (pytest)
# runtime only (no pytest):
# pip install -e ".[run]"
```

> Note: reinstalling the package with different extras may make pip remove
> previously installed ones — install both groups in a **single** command
> (`".[run,dev]"`) or just use `./install.sh` which handles it correctly.

> `-e` (editable) means the package runs straight from this source folder —
> don’t move/delete it, and always run from inside it so `plugins/` and
> `data/` resolve correctly.

**Step 2 — Create the `.env` config file:**

```bash
cp .env.example .env
nano .env
```

Fill at least these three keys with real values:

| Key | Where from | Purpose |
|---|---|---|
| `BOT_TOKEN` | [@BotFather](https://t.me/BotFather) → `/newbot` | bot authentication (required) |
| `API_ID` | [my.telegram.org](https://my.telegram.org) → API development tools | live run via Pyrogram |
| `API_HASH` | same place | live run via Pyrogram |
| `OWNER_ID` | your numeric id (e.g. via @userinfobot) | owner/sudo — needed even for `--check` |

Optional: `SUDO_IDS=111,222` (extra sudo ids), `GMB_DEFAULT_LANG=en|fa`
(default language), `GMB_DB_URL=sqlite:///data/…` (database location).

**Step 3 — Health check (no Telegram):**

```bash
python -m bot.main --check
```

Success output: “✅ هستهٔ پلاگین‌محور سالم است” plus the list of 51 plugins.

**Step 4 — Live run:**

```bash
set -a; source .env; set +a        # load the variables into this shell
python -m bot.main --run           # run
python -m bot.main --run --watch   # + auto hot-reload of plugins
```

Or simply use `./run.sh`, which reads `.env` for you.

**Step 5 — Tests (optional):**

```bash
pip install -e ".[dev]"
python -m pytest -q                # expected: 250 green tests
```

---

## فارسی — نکته‌ها / English — Notes

- **نصب مجدد / reinstall:** اگر وابستگی‌ها را به‌هم ریختید، پوشهٔ `.venv` را
  حذف و دوباره `./install.sh` اجرا کنید. داده‌های شما در `data/` و تنظیمات در
  `.env` می‌مانند.
- **به‌روزرسانی / updates:** `git pull` در همین پوشه و سپس
  `./install.sh` (نصب دوبارهٔ پکیج؛ `.env` و `data/` دست نمی‌خورند).
- **حذف کامل / uninstall:** `rm -rf .venv data` و حذف `.env` (اختیاری).
- **اجرا روی سرور / running on a server:** برای اجرای همیشگی از
  `systemd`/`tmux`/`screen` استفاده کنید؛ فرمان پایه همان
  `./run.sh --run --watch` است.
- **بدون تلگرام / without Telegram:** `--check` و همهٔ ۲۵۰ تست بدون توکن و
  بدون اینترنت اجرا می‌شوند (Pyrogram اختیاری/لِیزی ایمپورت می‌شود).
