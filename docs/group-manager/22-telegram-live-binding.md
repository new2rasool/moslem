# ماژول ۲۲ — اتصال زندهٔ همهٔ پلاگین‌ها به تلگرام (Telegram Binding)

تا اینجا هر پلاگین «فرمان/رویداد/دکمه/اکشن» را در هسته ثبت می‌کرد اما هیچ
لایه‌ای آن را به یک پیام‌رسان واقعی وصل نمی‌کرد. این ماژول همان اتصال است:
یک **آداپتور تلگرام** که با پیام‌های واقعی، ورود/خروج عضوها، کلیک روی
دکمه‌ها و… همهٔ ۵۱ پلاگین (۴۴ نسل قبل + ۷ پلاگین نسل نهم) را تغذیه می‌کند
و خروجی‌ها/اکشن‌های فیزیکی/خطوط کانال لاگ را در تلگرام اجرا می‌کند.

---

## ۱. جایگاه در معماری

```
Pyrogram (تلگرام)  ──آپدیت──►  bot/adapter/pyrogram_app.py
                                    │  تبدیل به مدل (بدون وابستگی به pyrogram)
                                    ▼
                              bot/adapter/connector.py  (TelegramConnector)
                                    │
        ┌───────────────────────────┼───────────────────────────────┐
        ▼                           ▼                               ▼
   فرمان/رویداد/دکمه           پاسخ‌ها/دکمه‌های شیشه‌ای          اکشن‌ها + لاگ
   dispatcher ← host.emit     out_sink → send_message          action_sink/audit_sink
        │                                                          │
        ▼                                                          ▼
   51 پلاگین                                           delete/ban/mute/kick/promote/…
```

- `bot/adapter/models.py` — مدل‌های مستقل از کتابخانه:
  `IncomingUser`، `IncomingChat`، `IncomingMessage` (با `service` برای
  ورود/خروج، `forwarded`، `content_type`، reply)، `IncomingCallback`.
- `bot/adapter/connector.py` — `TelegramConnector(host, dispatcher, client)`:
  کل منطق اتصال، **بدون هیچ وابستگی به pyrogram**؛ کلاینت فقط باید duck-typed
  پروتکلِ زیر را داشته باشد (همین باعث می‌شود همهٔ تست‌ها با کلاینت جعلی و
  بدون اینترنت اجرا شوند).
- `bot/adapter/pyrogram_app.py` — `PyrogramApp`: تنها جایی که pyrogram ایمپورت
  می‌شود (اختیاری/لِیزی)؛ آپدیت‌ها را به مدل‌ها تبدیل و هندلرها را ثبت می‌کند.

## ۲. پروتکل کلاینت (duck-typed)

کانکتور فقط به این متدهای `async` نیاز دارد (تبدیل به pyrogram در لایهٔ
بعدی؛ فعلاً روی دادهٔ خام):

| متد | معنی |
|---|---|
| `send_message(chat_id, text, *, reply_to=None, buttons=None)` | ارسال پاسخ (دکمه‌ها آرایهٔ `[[{text,data}]]`) |
| `delete_messages(chat_id, message_id)` | حذف فیزیکی پیام |
| `restrict(chat_id, user_id, *, muted, until=None)` | محدود/ساکت (و رفع با `muted=False`) |
| `ban(chat_id, user_id)` / `kick(chat_id, user_id)` | بن / اخراج |
| `lock_join(chat_id, locked)` | بستن/بازکردن ورود اعضا |
| `promote(chat_id, user_id, role=None)` / `demote(chat_id, user_id)` | ارتقا/عزل |
| `answer_callback(callback_id, text="")` | پاسخِ «کلیک دریافت شد» به تلگرام |

## ۳. مسیرهای ورودی (چه چیزی به کدام پلاگین می‌رسد)

- **فرمان متنی** (`/ban …`، «بن …»، …) → `dispatcher.try_dispatch_command`:
  هر ۱۳۲ فرمان از ۵۱ پلاگین + `/help` پویا، `/start`، `/plugins`.
- **پیام عادی** → رویداد `message`: به ترتیب اولویت به پلاگین‌هایی که شنوندهٔ
  `message` ثبت کرده‌اند می‌رسد (capsguard، antirepeat، antiflood، mediaflood،
  autorole، afk، slowmode، newcomer_guard، wordguard، …). رسانه‌ها با
  `content_type` (photo/video/animation/document/voice/video_note/sticker/
  audio/poll) و فورواردها با `is_forward` + `forward_from_chat_id`.
- **ورود عضو** (رویداد `member_joined`) → captcha، joinapprove، antiraid،
  nameguard، digest، greeter/rules/autowelcome…؛ **خروج** (`member_left`) →
  greeter و شمارندهٔ digest. ورودها در یک پیام سرویسِ چندنفره یک‌به‌یک
  پردازش می‌شوند (ربات خودش از فهرست حذف می‌شود).
- **کلیک دکمه** (`callback`) → هفت پیشوند ثبت‌شده:

| پیشوند دکمه | پلاگین | نمونه |
|---|---|---|
| `captcha:` | captcha | پاسخ کپچای ورود (عدد درست → رفع محدودیت) |
| `ja:` | joinapprove | تأیید/رد درخواست ورود توسط مدیر |
| `poll:` | polls | رأی در نظرسنجی |
| `reportop:` | reportops | رسیدگی مدیر به گزارش (warn/kick/ban/ignore) |
| `vk:` | votekick | رأی موافق/مخالف اخراج |
| `lot:` | lottery | شرکت در قرعه‌کشی |
| `faq:` | faq | دکمه‌های پرسش/پاسخ/صفحهٔ فهرست پرسش‌های متداول |

  کانکتور نام/یوزرنمِ کلیک‌کننده را از کاربرِ callback به پلاگین می‌رساند
  (`sender_name`/`sender_username`) تا مثلاً قرعه‌کشی نامِ واقعی ثبت کند.

## ۴. مسیرهای خروجی

- **پاسخ‌ها**: هرچه پلاگین‌ها با `ctx.respond` / `host.send_text` تولید کنند
  در صف کانکتور جمع و در پایانِ پردازشِ همان آپدیت ارسال می‌شود
  (`_flush`). دکمه‌های شیشه‌ایِ همان پردازش فقط به **آخرین** پیامِ آن
  پاسخ‌ها می‌چسبند (صفحه‌کلیدِ کهنه از پیام قبلی تکرار نمی‌شود).
- **اکشن‌های فیزیکی** (`ctx.act` / `host.push_action`) با یک صف مجزا اجرا
  می‌شوند؛ نگاشت `_run_actions`:

| اکشن پلاگین | تماس با کلاینت |
|---|---|
| `delete_message` | `delete_messages(chat, message_id)` (شناسهٔ پیامِ همان آپدیت) |
| `restrict`/`mute` | `restrict(chat, uid, muted=True, until=seconds)` |
| `unrestrict`/`unmute` | `restrict(chat, uid, muted=False)` |
| `ban` / `kick` | `ban` / `kick` |
| `lock_join` / `unlock_join` | `lock_join(chat, True/False)` |
| `promote` (+ `role`) / `demote` | `promote(chat, uid, role=…)` / `demote(chat, uid)` |

  نمونه‌ها: کپچا هنگام ورود `restrict` می‌کند و بعد از پاسخ درست
  `unrestrict`؛ capsguard/antirepeat/mediaflood پیام را `delete` می‌کنند؛
  joinapprove/nameguard/votekick `kick`/`unrestrict`؛ roles_admin
  `promote`/`demote`؛ antiraid `lock_join`/`unlock_join` (رهاسازی خودکار با
  `on_tick`).
- **خطوط کانال لاگ**: `api.record_action` → رویداد داخلی `action_recorded` →
  پلاگین audit یک خط استاندارد می‌سازد → `audit_sink` کانکتور آن را به
  `log_channel` گروه (تنظیم با `/setlog`) و اگر تنظیم نشده به خودِ گروه
  می‌فرستد. همهٔ اکشن‌های مهم (ban/kick/mute/warn/promote/demote/auto:*/
  join_approve/join_deny/report) از این مسیر عبور می‌کنند.

## ۵. اجرای واقعی

```bash
pip install pyrogram

# .env (یا متغیر محیط):
BOT_TOKEN=123456:ABC…          # توکن بات (از @BotFather)
API_ID=1234567                 # از my.telegram.org
API_HASH=abcdef…
OWNER_ID=123456789             # آیدی عددی مالک (اجباری)

python -m bot.main --run               # اجرای زنده
python -m bot.main --run --watch       # + هات‌ری‌لود پوشهٔ plugins
```

- `--check` بدون توکن کار می‌کند (بررسی سلامت + شمارش پلاگین‌ها/فرمان‌ها).
- pyrogram فقط در `PyrogramApp` ایمپورت می‌شود؛ هسته/کانکتور/تست‌ها بدون آن
  می‌مانند (تست‌ها با `FakeClient` پروتکل بالا اجرا می‌شوند).
- `OWNER_ID`/`BOT_TOKEN` همیشه لازم‌اند؛ `API_ID`/`API_HASH` فقط هنگام
  `--run` اعتبارسنجی می‌شوند.
- دیتابیس sqlite و جلسهٔ pyrogram در `data/` پروژه ساخته می‌شوند.

## ۶. تست‌ها

`tests/test_telegram_connector.py` با `FakeClient` (ضبط‌کنندهٔ تماس‌ها)
پروتکل و مسیرهای بالا را بدون اینترنت می‌سنجد:

- فرمان → پاسخ به همان گروه؛
- روشن‌کردن capsguard → حذف فیزیکی پیامِ جیغ + هشدار؛
- ورود عضو با کپچای روشن → `restrict` + پیام دکمه‌دار؛ کلیک درست →
  `unrestrict` + `answer_callback`؛
- `/mute` `/ban` `/kick` `/unmute` → اکشن‌های فیزیکیِ متناظر؛
- `/setlog` → خطوط حسابرسی به کانال لاگ؛ `/promote`/`/demote` → ارتقا/عزل واقعی.

`pytest` → **۲۵۰ تست سبز** · بارگذاری: **۵۱ پلاگین، ۱۳۲ فرمان**.
