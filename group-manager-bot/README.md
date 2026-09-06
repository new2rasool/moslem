# 🧩 group-manager-bot — ربات مدیریت گروه با هستهٔ پلاگین‌محور

هستهٔ ربات که **هیچ قابلیتی را نمی‌شناسد**؛ همهٔ قابلیت‌ها «پلاگین» هستند و به‌صورت خودکار از
پوشهٔ `plugins/` کشف و بارگذاری می‌شوند. افزودن/به‌روزرسانی/حذف قابلیت = فقط مدیریت پوشهٔ
`plugins/` — **بدون تغییر در هسته**.

> معماری کامل: [`docs/group-manager/12-plugin-architecture.md`](../docs/group-manager/12-plugin-architecture.md)

## ✨ چرا پلاگین‌محور؟

- **به‌روزرسانی قابلیت:** فایل پلاگین را عوض کنید → هات‌ری‌لود خودکار (`--watch`)؛ هسته دست نمی‌خورد.
- **افزودن قابلیت:** پوشهٔ جدید در `plugins/` بسازید → ربات خودکار آن را به فرمان‌ها و
  فهرست `/help` اضافه می‌کند.
- **حذف قابلیت:** پوشه را بردارید یا `/plugin unload <name>` بزنید.
- **ایزوله‌سازی خطا:** پلاگین خطادار بقیه را نمی‌شکند.
- **قابلیت‌های جدید = پلاگین‌های جدید** (بدون نیاز به تغییر main/هسته).

## 🧱 معماری

```
plugins/<name>/plugin.py   ← قابلیت (قرارداد: PLUGIN_VERSION + register(api))
        │  register(api)
        ▼
هسته:  PluginHost(کشف/ری‌لود/emit داخلی) ← Registry(ثبت فرمان/رویداد/دکمه)
        Dispatcher(مسیریابی + سطح دسترسی + انزوا + action_sink)
        services/access · domain/* · repositories · db · cache · i18n

اجرای فیزیکی: پلاگین‌ها «اکشن ساختاریافته» (ctx.act / api.record_action) تولید
می‌کنند؛ آداپتورِ تلگرام آن‌ها را از action_sink (حذف/محدودیت) و audit_sink
(ارسال به کانال لاگ) اجرا می‌کند.
```

لایه‌های خالص (domain) همان‌ها هستند؛ فقط «قابلیت‌ها» از هسته به پلاگین‌ها منتقل شده‌اند.

## 📦 پلاگین‌های نمونه (در plugins/)

| پلاگین | نمونهٔ | نشان‌دهندهٔ |
|---|---|---|
| `ping` | `/ping`, «پینگ» | ساده‌ترین فرمان + ترجمهٔ اختصاصی |
| `whoami` | `/whoami`, `/id` | دسترسی به `api.access` برای نمایش سطح کاربر |
| `admin_utils` | `/duration 1d6h30m` (MOD+) | چک سطح دسترسی توسط هسته + استفاده از domain |
| `greeter` | رویداد ورود/خروج عضو + `setgreet` | رویدادمحور + متن سفارشی گروه |
| `moderation` | `ban/kick/mute/tmute/warn/recent` | تنبیه پلکانی + مصونیت سطوح + دفتر حسابرسی |
| `antiflood` | رویداد `message` + `setflood` | ضد سیل پنجره‌ای + معافیت ادمین |
| `locks` | `lock/unlock/locks` + لیست سفید دامنه | قفل url/forward/رسانه با اکشن ساختاریافته |
| `wordguard` | `addblacklist/rmblacklist/…` | فیلتر کلمات سیاه با نرمال‌سازی ضد دورزدن |
| `audit` | `setlog/log/logtest` | کانال لاگ: قالب‌بندی خودکار action_recorded |
| `roles_admin` | `promote/demote/adminlist` | ارتقا/عزل با سلسله‌مراتب + ثبت در حسابرسی |
| `captcha` | رویداد ورود عضو + دکمه‌های شیشه‌ای | کپچای ورود تعاملی + اخراج خودکار در مهلت |
| `antiraid` | `antiraid/raid/raidset` | تشخیص موج ورود + قفل خودکار و رهاسازی |
| `filters` | `addfilter/rmfilter/filters` | پاسخ خودکار کلیدواژه‌ای با نرمال‌سازی |

فرمان‌های خود هسته (بدون پلاگین): `/start`، `/help` (فهرست پویا)، `/plugins`،
`/plugin load|unload|reload|reloadall` (سودو، پیوی) و
`/pluginenable <name> <on|off>` (ادمین، برای خاموش‌کردن پلاگین در همان گروه).

## ▶️ اجرا

```bash
# بررسی سلامت + کشف خودکار پلاگین‌ها (بدون تلگرام/توکن)
python3 -m bot.main --check

# تست‌ها (۱۶۹ تست — منطق ناب، بدون تلگرام)
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
make test

# اجرای واقعی (بعد از پر کردن .env با BOT_TOKEN) + هات‌ری‌لود
.venv/bin/pip install -e ".[run]"
python3 -m bot.main --run --watch
```

## 🧩 افزودن یک پلاگین جدید (۳۰ ثانیه)

```bash
mkdir -p plugins/echo/locales
```

```python
# plugins/echo/plugin.py
PLUGIN_VERSION = "1.0.0"

def register(api):
    async def echo(ctx):
        ctx.respond(api.tr(ctx.lang, "echoed", text=ctx.args or "…"))
    api.register_command("echo", echo, aliases=("echo", "اکو"), usage="echo <text>")
```

```json
// plugins/echo/locales/fa.json
{ "echoed": "🔁 {text}" }
```

```json
// plugins/echo/locales/en.json
{ "echoed": "🔁 {text}" }
```

رباتِ در حال اجرا با `--watch` حداکثر تا ۱ ثانیهٔ دیگر فرمان `/echo` را دارد
(بدون ری‌استارت، بدون تغییر هسته). همین‌جا امتحان کنید:

```bash
# بعد از ساخت پوشهٔ بالا، در همان ترمینال:
python3 -m bot.main --check   # پلاگین echo در فهرست می‌آید
```

## 🗂 ساختار سورس

```
bot/
├── main.py            # بوت‌استرپ: DB → repos → access → host → dispatcher
├── plugin_host.py     # کشف، بارگذاری/ری‌لود خودکار، نظارت (--watch)
├── registry.py        # ثبت فرمان/رویداد/دکمه + حل تعارض
├── dispatcher.py      # پارس، سطح دسترسی، توزیع، ایزوله‌سازی خطا
├── plugin_api.py      # PluginAPI — مرز پلاگین‌ها با هسته
├── context.py         # CommandContext/EventContext/CallbackContext
├── host_system.py     # فرمان‌های سیستمی هسته (help/plugins/plugin)
├── domain/            # منطق ناب (بدون وابستگی): roles, duration, text_normalize, flood
├── services/          # access_service (سطح مؤثر کاربر)
├── repositories/      # اینترفیس + SQLite (آماده برای PostgreSQL)
├── db/  cache/  i18n/ config.py  logging_setup.py
└── handlers/base.py   # ابزار چک دسترسی (برای آداپتورها)
plugins/               # ← همهٔ قابلیت‌ها این‌جا (کشف خودکار)
tests/                 # ۱۶۹ تست (unit + پلاگین + E2E بدون تلگرام)
```

## 🛣 وضعیت و قدم‌های بعدی

- ✅ فاز ۰–۱: اسکلت لایه‌ای + هستهٔ پلاگین‌محور + کشف/ری‌لود خودکار + i18n + نقش/دسترسی
- ⏭️ فاز ۲: آداپتور کامل Pyrogram (کشف خالق گروه، callback های واقعی، اجرای فیزیکی
  ban/mute)، سپس تبدیل ماژول‌های سند (قفل‌ها، فیلتر کلمات، CAPTCHA و…) به پلاگین‌های مستقل.

## 📚 مستندات مرتبط

- [`docs/group-manager/`](../docs/group-manager/README.md) — کتابخانهٔ کامل مشخصات (۱۳ سند)
- `docs/group-manager/11-development-workflow.md` — فرایند توسعه (چرا این‌گونه ساختیم)
- `docs/group-manager/12-plugin-architecture.md` — قرارداد و جزئیات پلاگین‌ها
- `docs/group-manager/13-advanced-plugins.md` — پلاگین‌های پیشرفتهٔ پیاده‌سازی‌شده
