# 🧩 moslem — ربات مدیریت گروه تلگرام (پلاگین‌محور) / Telegram Group Manager Bot

یک ربات حرفه‌ای مدیریت گروه تلگرام با **هستهٔ پلاگین‌محور** که خودش هیچ
قابلیتی را نمی‌شناسد؛ همهٔ ۵۱ قابلیت (مدیریت، ضداسپم، کپچا، رأی‌گیری،
قرعه‌کشی، آمار، پشتیبان‌گیری و…) پلاگین هستند و خودکار بارگذاری می‌شوند.

A professional Telegram group-manager bot with a **plugin-driven core** that
knows no features itself: all 51 capabilities are auto-discovered plugins.

```
docs/                     ← ۲۴ سند تفصیلی (فارسی) / detailed specs (FA)
group-manager-bot/        ← سورس کامل ربات / the bot source (FA + EN)
```

## ⚡ شروع سریع / Quick start

```bash
cd group-manager-bot
./install.sh              # نصب خودکار / automatic install
# سپس / then:  ویرایش .env  ← BOT_TOKEN ،API_ID ،API_HASH ،OWNER_ID
./run.sh --run --watch    # اجرای زنده / live run
```

- 🇮🇷 نصب خودکار و دستی (فارسی): [`docs/group-manager/24-installation.md`](docs/group-manager/24-installation.md)
- 🇬🇧 Automatic & manual install (English): [`docs/group-manager/24-installation.md`](docs/group-manager/24-installation.md)
- نصب بدون تلگرام: `python3 -m bot.main --check` · تست‌ها: `python3 -m pytest -q` (۲۵۰ تست)

## 📁 انبارها / Repositories

| پوشه | محتوا |
|---|---|
| `group-manager-bot/` | سورس ربات (هسته + ۵۱ پلاگین + آداپتور تلگرام + ۲۵۰ تست) |
| `docs/group-manager/` | مشخصات تفصیلی ۲۴ ماژول (فارسی) از دروازهٔ ورود تا معماری پلاگین |
| `docs/group-manager-features-fa.md` | مشخصات جامع اولیهٔ ربات |
