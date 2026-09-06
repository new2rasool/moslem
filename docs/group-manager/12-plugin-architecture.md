# ماژول ۱۲ — معماری پلاگین‌محور (Plugin Architecture)

این سند، طراحی و قراردادهای **هستهٔ پلاگین‌محور** را شرح می‌دهد که به‌صورت واقعی در
[`group-manager-bot/`](../../group-manager-bot/README.md) پیاده‌سازی شده است.

---

## ۱. هدف

> **به‌روزرسانی و افزودن قابلیت = فقط «مدیریت پوشهٔ plugins»؛ بدون هیچ تغییری در هسته.**

- قابلیت‌های ربات **پلاگین** هستند، نه بخشی از هسته.
- هسته فقط «چارچوب» است: کشف پلاگین، ثبت‌نام، مسیریابی، سطح دسترسی، i18n، خطا.
- افزودن پوشه/فایل پلاگین جدید → ربات آن را خودکار کشف و به فرمان‌ها/رویدادهایش اضافه می‌کند.
- ویرایش فایل پلاگین → هات‌ری‌لود (بدون ری‌استارت) رفتار را عوض می‌کند.

## ۲. نمای کلی اجزا

```
                ┌──────────────────────────────────────────────────┐
                │                    هسته (Core)                    │
                │  plugin_host  → کشف/بارگذاری/ری‌لود/نظارت          │
                │  registry     → ثبت فرمان/رویداد/دکمه             │
                │  dispatcher   → مسیریابی + چک سطح دسترسی + انزوا   │
                │  services     → access (سطح مؤثر کاربر) و…         │
                │  domain       → قواعد ناب (roles/flood/duration)   │
                │  db/repo/cache/i18n/config                        │
                └───────▲──────────────────────▲───────────────────┘
                        │ register(api)        │ اجرای هندلر (ctx)
                ┌───────┴─────────┐   ┌─────────┴──────────┐
                │  پلاگین‌ها       │   │ آداپتور (تلگرام/تست) │
                │ plugins/*/plugin.py │  → try_dispatch_command / dispatch_event
                └─────────────────┘   └────────────────────┘
```

**قانون اصلی:** پلاگین‌ها فقط با `PluginAPI` (`api`) و اشیاء Context کار می‌کنند و
به داخل هسته دسترسی ندارند؛ هسته هم هیچ قابلیتی را نمی‌شناسد.

## ۳. ساختار پوشهٔ پلاگین‌ها

```
plugins/
├── ping/
│   ├── plugin.py          ← قرارداد پلاگین
│   └── locales/
│       ├── fa.json        ← ترجمهٔ اختصاصی پلاگین (فارسی)
│       └── en.json        ← ترجمهٔ اختصاصی (انگلیسی)
├── whoami/
│   └── plugin.py
├── greeter/
│   └── plugin.py
└── my_new_feature/         ← پلاگین جدیدِ شما (بدون تغییر هسته)
    ├── plugin.py
    └── locales/…
```

هر دو شکل «پوشه با plugin.py» و «فایل تکی `.py`» پشتیبانی می‌شود.

## ۴. قرارداد (Contract) هر پلاگین

```python
# plugins/my_new_feature/plugin.py
PLUGIN_VERSION = "1.0.0"                      # اختیاری

def register(api) -> None:                     # الزامی
    # ۱) فرمان با نام‌های مستعار فارسی/انگلیسی و حداقل سطح دسترسی
    api.register_command(
        "warn",
        on_warn,
        level=AccessLevel.MOD,                 # از bot.domain.roles
        aliases=("warn", "هشدار"),
        usage="warn [دلیل]",
    )

    # ۲) رویداد (مثل پیوستن عضو)
    api.register_event("member_joined", on_join, priority=100)

    # ۳) دکمهٔ شیشه‌ای
    api.register_callback("myfeature:approve:", on_button)

async def on_warn(ctx) -> None:                # هندلر فرمان
    ctx.respond(api.tr(ctx.lang, "warn_done", name=ctx.args))

async def on_join(ctx) -> None:                # هندلر رویداد
    ctx.respond("خوش آمدی " + ctx.data.get("member_name", ""))

async def on_button(ctx) -> None:              # هندلر دکمه
    ctx.respond("payload=" + ctx.payload)
```

### عناصر Context (مستقل از تلگرام)
| Context | فیلدهای مهم | روش پاسخ |
|---|---|---|
| `CommandContext` | `plugin, command, args, user_id, chat_id, is_private, lang, sender_name, reply_to_user_id` | `ctx.respond(text)` |
| `EventContext` | `kind, chat_id, user_id, user_name, data` | `ctx.respond(text)` |
| `CallbackContext` | `prefix, action, payload, user_id, chat_id` | `ctx.respond(text)` |

### API در دسترس پلاگین (`api`)
- `api.tr(lang, key, **fmt)` — ترجمه (اول لوکال خودِ پلاگین، بعد fallback به هسته)
- `api.register_command / register_event / register_callback`
- `api.access.level(chat_id, user_id)` — سطح مؤثر کاربر
- `api.cfg` — پیکربندی · `api.cache` — کش · `api.groups/users/roles` — ریپازیتوری‌ها
- `api.log` — Logger اختصاصی · `api.host` — میزبان (برای مدیریت/اطلاعات)

## ۵. چرخهٔ عمر پلاگین و هات‌ری‌لود

| رویداد در پوشهٔ plugins | رفتار خودکار هسته |
|---|---|
| افزودن پوشه/فایل پلاگین | کشف و بارگذاری + ثبت فرمان/رویداد (ظاهر در /help) |
| ویرایش فایل پلاگین | unload قدیمی + بارگذاری نسخهٔ جدید (رفتار جدید، هسته دست‌نخورده) |
| حذف فایل پلاگین | unload کامل و پاک‌سازی ردپا از رجیستری |
| پلاگین خطادار در register | ثبت به‌عنوان `failed` با پیام خطا؛ بقیهٔ پلاگین‌ها سالم می‌مانند |
| تداخل نام فرمان/نام مستعار | پلاگین دوم رد می‌شود؛ اولی و بقیه کار می‌کنند |

- تشخیص تغییر با **hash محتوای فایل** (نه فقط mtime) انجام می‌شود.
- اجرای پلاگین **مستقیماً از سورس با `compile()`** است (نه import کش‌دار) تا کش بایت‌کد
  پایتون (`__pycache__`) هات‌ری‌لود را نشکند.
- خطای runtime در یک هندلر: لاگ + پیام خطای عمومی؛ پلاگین‌های دیگر ادامه می‌دهند.

## ۶. فرمان‌های مدیریت پلاگین (خود هسته)

| فرمان | سطح | کار |
|---|---|---|
| `/help` | همه | فهرست پویای فرمان‌ها از پلاگین‌های بارگذاری‌شده |
| `/plugins` | همه | وضعیت پلاگین‌ها (نسخه، شمار فرمان/رویداد/دکمه) |
| `/plugin list` | سودو (پیوی) | فهرست |
| `/plugin load <name>` | سودو (پیوی) | بارگذاری بدون ری‌استارت |
| `/plugin unload <name>` | سودو (پیوی) | حذف از حافظه |
| `/plugin reload <name>` | سودو (پیوی) | ری‌لود یک پلاگین |
| `/plugin reloadall` | سودو (پیوی) | اعمال همهٔ تغییرات پوشهٔ plugins |
| اجرا با `--watch` | — | نظارت خودکار هر ۱ ثانیه روی پوشه |

## ۷. گسترش رویدادها و دکمه‌ها

- رویدادهای استاندارد (ثابت در `bot.registry`): `member_joined`، `member_left` — در فازهای
  بعد `message`، `edited_message` و… افزوده می‌شود (همان ثابت‌ها، بدون تغییر پلاگین‌ها).
- دکمه‌ها با **prefix بلندترین‌مطابقت** مسیریابی می‌شوند: `myfeature:approve:` دقیق‌تر از `myfeature:` است.
- پلاگین‌ها می‌توانند با `api.register_callback` پیشوند دلخواه خودشان را بگیرند.

## ۸. توسعهٔ یک پلاگین جدید — گام‌به‌گام

1. پوشه بسازید: `plugins/<name>/`
2. `plugin.py` با `PLUGIN_VERSION` و `register(api)`
3. فرمان/رویداد/دکمه ثبت کنید (کلید ترجمه در `locales/fa.json` و `en.json`)
4. هندلر را با `ctx.respond` بنویسید (async)
5. در صورت نیاز از `api.access.level` برای نمایش/تصمیم‌گیری و `api.groups` برای تنظیمات گروه استفاده کنید
6. بدون ری‌استارت: هسته با `--watch` پلاگین را خودکار بارگذاری می‌کند؛ یا `/plugin reload <name>`

**تست پلاگین:** مانند `tests/test_plugins_e2e.py` — کافی است پوشهٔ پلاگین را با
`PluginHost` بارگذاری و از `Dispatcher` صدا بزنید؛ **بدون نیاز به تلگرام واقعی**.

## ۹. محدودیت‌های امنیتی و مرزها

- پلاگین‌ها «کد قابل‌اعتماد» در نظر گرفته می‌شوند (مدیر نصبشان می‌کند)؛ برای پلاگین
  از منابع متفرقه، بازبینی دستی لازم است.
- هسته، سطح دسترسی هر فرمان را خودش چک می‌کند؛ پلاگین نباید نقش «ادمین» را شبیه‌سازی کند.
- نام پلاگین‌ها یکتا و در معرض دید در /help است؛ تداخل نام فرمان خطای شفاف دارد.
- `private_only`/`group_only` تضمین‌کنندهٔ محل اجرای فرمان است.
