# ماژول ۱۰ — مهندسی، مدل داده، امنیت و نقشهٔ راه (Engineering & Data)

---

## ۱۰.۱. مدل داده (Schema پیشنهادی — PostgreSQL)

### جدولها
```sql
groups(
  chat_id BIGINT PK, title TEXT, username TEXT, preset TEXT, lang TEXT DEFAULT 'fa',
  tz TEXT DEFAULT 'Asia/Tehran', log_channel BIGINT, log_level TEXT DEFAULT 'standard',
  approved BOOL DEFAULT TRUE, active BOOL DEFAULT TRUE,
  settings JSONB NOT NULL DEFAULT '{}'   -- تنظیمات همهٔ ماژولها (۸.۷)
);
users(user_id BIGINT PK, lang TEXT, trust_score INT DEFAULT 0, created_at TIMESTAMPTZ);
group_roles(chat_id BIGINT, user_id BIGINT, role TEXT, title TEXT, by BIGINT, at TIMESTAMPTZ,
            PK(chat_id,user_id), INDEX(user_id));
warns(chat_id BIGINT, user_id BIGINT, n INT, active JSONB, PK(chat_id,user_id), INDEX(user_id));
blacklist(chat_id BIGINT, word TEXT, mode TEXT, PK(chat_id,word));
filters(chat_id BIGINT, keyword TEXT, payload JSONB, PK(chat_id,keyword));
locks(chat_id BIGINT, item TEXT, action SMALLINT, until TIMESTAMPTZ NULL, PK(chat_id,item));
gban(user_id BIGINT PK, reason TEXT, by BIGINT, at TIMESTAMPTZ);
feds(fed_id TEXT PK, name TEXT, token TEXT, admin BIGINT);
fed_bans(fed_id TEXT, user_id BIGINT, reason TEXT, PK(fed_id,user_id));
msg_counts(chat_id BIGINT, user_id BIGINT, day DATE, n INT, PK(chat_id,user_id,day));
timers(id BIGINT GENERATED, chat_id BIGINT, name TEXT, spec JSONB, next_run TIMESTAMPTZ, active BOOL);
logs(chat_id BIGINT, at TIMESTAMPTZ, event TEXT, payload JSONB);   -- ۹۰ روز retention
broadcast_jobs(id BIGINT, status TEXT, payload JSONB);
```

### قواعد داده
- **JSONB برای settings:** افزودن قابلیت جدید = بدون Migration.
- ایندکسهای ضروری: `msg_counts(chat_id, day)`, `warns(user_id)`, `timers(next_run)`.
- ارتباطات با **Foreign Key اختیاری** (مقیاس بالا) و `ON DELETE CASCADE` برای پاکسازی گروه.
- شمارندههای لحظهای (flood, captcha state) در **Redis با TTL** — نه در SQL.

---

## ۱۰.۲. مدیریت Rate-Limit و خطاها (۴۲۹ و همخانوادهها)

| مسئله | راهحل |
|---|---|
| خطای 429 | خواندن `X-Retry-After`؛ صف داخلی `PriorityQueue`؛ ارسال بعدی پس از retry؛ ثبت معیار سلامت |
| FloodWait | `asyncio.sleep` هوشمند — هرگز Blocking `time.sleep` |
| `MessageEmpty`, `MessageTooLong` | try/except اختصاصی + پاسخ کوتاه |
| قطع اینترنت (ConnectionError) | حلقهٔ reconnect با Backoff نمایی (۱s→۲s→۴s… سقف ۶۰s) + «حالت آفلاین» و ازسرگیری صفها |
| خطای `PeerIdInvalid` (ربات اخراج شده) | ثبت + توقف خودکار ماژولهای آن گروه |
| استثنای پیشبینینشده | `try/except Exception` در هر هندلر + `logger.exception` + ادامهٔ کار (کراش ممنوع) |

- هر هندلر داخل `@safe_handler` دکوریتور: خطا → لاگ + (در حالت full) ارسال به کانال خطای مالک.

---

## ۱۰.۳. کش و کارایی

| داده | کش | TTL | چرا |
|---|---|---|---|
| تنظیمات گروه | حافظه/Redis | ۳۰s | هر پیام ۱ بار |
| اعضای ادمین/Mod گروه | حافظه | ۶۰s | چک دسترسی هر دستور |
| سن اکانت | Redis | ۲۴h | UserFullInfo گران است |
| نتیجهٔ CAS | Redis | ۲۴h | API خارجی |
| شمارندهٔ ضد سیل | Redis | ۵s | دقت لحظهای |
| جلسهٔ CAPTCHA | Redis | ۱۲۰s | پیامهای زنده |

- هر پیام ورودی باید **< ۵ms** هزینهٔ سربار داشته باشد (بدون Query مستقیم در مسیر داغ).
- آمار پیام با Batch-insert هر ۵ ثانیه (کاهش IO) و Flush در خاموشی.

---

## ۱۰.۴. امنیت برنامه

| تهدید | دفاع |
|---|---|
| نفوذ به پنل مالک | دستورهای حساس = تأیید دومرحلهای + فقط از آیدیهای ثبتشده |
| سوءاستفادهٔ ادمین | سقف روزانه، Strict reason، مصونیت سلسلهمراتبی، لاگ + undo |
| پیام جعلی (Spoofing) | نادیدهگرفتن `from_user` ساختگی؟ (تلگرام امن است)؛ چک `sender_chat` در ضداسپم |
| بدافزار در لینکها | اسکن URL با `urllib`/سرویس امنیتی اختیاری + هشدار «لینک ناشناس» برای ادمین |
| Redis/SQL بدون رمز | رمز قوی، فقط Loopback، `requirepass` |
| لو رفتن توکن | چرخش توکن، لاگ اکشن، حداقل مجوزهای ربات (ماژول ۱.۱) |
| DoS روی ربات | محدودیت نرخ ورودی (پیشپردازش: ۱۰۰ پیام/ثانیه به ازای هر گروه در حالت بحرانی) |

### حداقل مجوزهای پیشنهادی ربات
`can_delete_messages`, `can_restrict_members`, `can_invite_users`, `can_pin_messages`, `can_manage_video_chats` — **نه** `can_promote_members` مگر ارتقای تلگرامی فعال شود (`--tg`).

---

## ۱۰.۵. معماری و مقیاس

```
[تلگرام] ⇄ [Worker اصلی (Pyrogram)] ⇄ [Redis] ⇄ [PostgreSQL]
                    │
              [Worker کمکی برای:]
              – آمار/aggregate (ساعت شلوغ)
              – Broadcast (صف مجزا)
              – تسکهای شبانه (APScheduler)
```
- **تکنسخه:** همهچیز در یک پروسه با `asyncio` + APScheduler (تا ۲۰۰ گروه بدون دردسر).
- **چندنسخه (Shard):** هر Worker گروههای مشخص (Hash بر chat_id)؛ صف Broadcast و GBan از طریق Redis Pub/Sub؛ پنل مالک روی Primary.
- **Healthcheck:** اندپوینت داخلی `stats` (پروسههای زنده، تأخیر Redis/DB، صفهای مانده).
- استقرار: Docker Compose (bot + redis + postgres) + systemd؛ لاگها به stdout برای جمعآوری.

---

## ۱۰.۶. بکاپ و بازیابی
- بکاپ روزانهٔ PostgreSQL (`pg_dump`) + Redis (فقط ساختار مهم نیست؛ TTL دارد) به فضای ابری.
- `export/import` گروه و سراسری (JSON) — نسخهگذاریشده (v1) برای سازگاری آینده.
- تمرین بازیابی: مستند + اسکریپت `restore.sh` تستشده.

---

## ۱۰.۷. تست و کیفیت (مرتبط با ماژولها)
| لایه | ابزار | پوشش |
|---|---|---|
| واحد (Unit) | pytest | پارسر زمان، نرمالسازی متن، سطوح دسترسی، انقضای هشدار |
| یکپارچه (Integ.) | pytest + mock API تلگرام | جریان CAPTCHA، گیت قوانین، Raid State Machine |
| E2E | ریال تلگرام تست | ورود/خروج، بن/آنبن، فیلترها |
| عملکرد | Locust (روی هندلر متن) | ۵۰ پیام/ثانیه بدون افت |
| پایداری | Chaos (قطع Redis، 429) | بدون کراش، بازیابی خودکار |

پوشش هدف: ۸۰٪+ خط کد ماژولهای امنیتی. هر باگ امنیتی = تست رگرسیون اجباری.

---

## ۱۰.۸. نقشهٔ راه اجرا (Roadmap با خروجی قابل اندازهگیری)

### فاز ۱ — MVP (هفته ۱–۲): هستهٔ قابل استفاده
- [ ] اسکلت پروژه + احراز سطح دسترسی + دوزبانه
- [ ] خوشآمد/خداحافظی/قوانین (+ دکمهٔ قوانین اختیاری)
- [ ] ضد سیل + بن/کیک/میوت زماندار + دلیل
- [ ] قفل url + فوروارد (دو قفل پرکاربرد)
- [ ] بلکلیست ساده + کانال لاگ (سطح minimal)
- **خروجی:** نصب در ۳ گروه واقعی و استفادهٔ روزمره.

### فاز ۲ — تکمیل (هفته ۳–۶)
- [ ] CAPTCHA + گیت قوانین + سپر اکانت تازه
- [ ] ضد راید + GBan + CAS
- [ ] هشدار چندسطحی + گزارش ناشناس
- [ ] همهٔ قفلها + قفل زماندار
- [ ] فیلترها/نوتها + پنل تنظیمات بصری + Preset ها
- [ ] purge/zombies/title + آمار پایه
- **خروجی:** پوشش ۹۰٪ چکلیست پیوست ب سند اصلی.

### فاز ۳ — حرفهای (هفته ۷–۱۰)
- [ ] فدراسیون + پنل کامل مالک + Broadcast مهندسیشده
- [ ] زمانبندی (Timer/Cron) + نمودارها
- [ ] کش Redis + معماری چندنسخه + Healthcheck
- [ ] بکاپ/export + تستهای E2E + CI
- **خروجی:** آمادهٔ سرویسدهی به ۱۰۰+ گروه با SLA ۹۹٪.

---

## ۱۰.۹. جمعبندی شاخصهای «حرفهایبودن»
| شاخص | هدف |
|---|---|
| زمان پاسخ ربات (p95) | < ۴۰۰ms |
| آپتایم | ۹۹.۵٪ |
| اکشنهای اشتباه (False-positive) | < ۰.۱٪ پیامهای حذفشده |
| زمان نصب یک گروه جدید | < ۲ دقیقه (بدون کدنویسی) |
| پشتیبانی زبان | ۲ (معماری آماده برای +N) |
| بازیابی از خرابی | خودکار < ۶۰ ثانیه |
