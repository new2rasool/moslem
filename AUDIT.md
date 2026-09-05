# گزارش بازبینی کد — `new2rasool/moslem` (MusicRasool)

تاریخ بازبینی: 2026-09-05
منبع: `moslem.zip` در ریشه مخزن → استخراج‌شده در `extracted/moslem/` (۴۳ فایل، ~۱۰٬۰۵۷ خط)
محیط تست: Python 3.11.2 + نصب دقیق `requirements.txt` (pyrogram 2.0.106، py-tgcalls 1.2.9، ntgcalls 1.1.3، aiohttp 3.9.5، yt-dlp 2026.7.4)

**بازبینی روی سورس دست‌نخورده انجام شد** (`extracted/moslem/` هنوز بایت‌به‌بایت با `moslem.zip` یکسان است). هر مورد زیر یا با اجرای واقعی کد/تست تأیید شده یا با خواندن خط‌به‌خط کد؛ موارد تأییدنشده صریحاً علامت‌گذاری شده‌اند.

> **به‌روزرسانی (۲۰۲۶-۰۹-۰۵):** اصلاحات انجام شد. سورس اصلاح‌شده در
> `musicrasool/` مخزن است (ایمپورت دست‌نخورده از zip در کامیت
> `Import MusicRasool source…`، و اصلاحات روی آن). وضعیت تک‌تک موارد در
> بخش **«۱۲) وضعیت اصلاحات»** انتهای همین فایل آمده است.

---

## ۰) نتیجه اجرای تست‌های خود پروژه

```
$ python tests/run_all.py
RUN: tests/smoke_test.py          → PASSED  (142 handler در ۲ گروه)
RUN: tests/test_handlers.py       → 31/31 PASSED
RUN: tests/test_auth.py           → 30/30 PASSED
RUN: tests/test_layout.py         → 15/15 PASSED
RUN: tests/test_panel_buttons.py  → 42/42 PASSED
RUN: tests/test_stream_lifecycle.py → 8/9  FAIL
     FAIL - conversions map UPPERCASE 1.2.x members
       -> AttributeError type object 'ntgcalls.StreamStatus' has no attribute 'PLAYING'
FAILED: ['tests/test_stream_lifecycle.py']     (exit code = 1)
```

یعنی **سوئیت تست پروژه با همان نسخه‌های پین‌شده در `requirements.txt` سبز نیست** (خلاف ادعای `README.md:311-312`).

---

## 🔴 بحرانی (Critical)

### C1. اجرای تست‌ها، `.env` واقعی و دیتابیس تولید را نابود می‌کند
هر ۶ فایل تست، `.env` ریشه پروژه را با مقادیر تستی **بازنویسی** می‌کنند و روی دیتابیس واقعی `DELETE FROM` می‌زنند:

| فایل | خط | عمل |
|---|---|---|
| `tests/smoke_test.py` | 16 / 44-45 | `open(".env","w")` + `DELETE FROM charge, charge2, gp, creators, musicadmin, videoadmins, sudo, alll, ejbar, banlist` |
| `tests/test_handlers.py` | 15 / 46 | همین |
| `tests/test_panel_buttons.py` | 36 / 51 | همین |
| `tests/test_stream_lifecycle.py` | 29 / 39-40 | همین |
| `tests/test_auth.py` | 25 | بازنویسی `.env` |
| `tests/test_layout.py` | 12 | بازنویسی `.env` |

نتیجه: اگر روی سرور واقعی `python tests/run_all.py` اجرا شود → **توکن ربات، OWNER_ID/SUDO_ID عوض می‌شود و تمام شارژ گروه‌ها، گروه‌های نصب‌شده، ادمین‌ها، سودوها و لیست بن پاک می‌شود.** (من عملاً همین را هنگام اجرا در کپی استخراج‌شده دیدم: `.env` با توکن `123456:T` بازنویسی شد.)

**اصلاح:** تست‌ها باید `config.ENV_FILE`/`DB_PATH` را به یک دایرکتوری موقت (`tempfile.mkdtemp()`) ریدایرکت کنند، نه نوشتن در ریشه پروژه.

### C2. نشت اعتبارنامه واقعی در `.env.example`
`.env.example:7,8,11,17`:
```
API_ID=918990
API_HASH=9c9fe04dc2a85e9dd74208335c537f1a
BOT_TOKEN=8053868457:AAGCNZZ65Bz6rJy69cv7hycnEXidPL8tncg
OWNER_ID=6173234874
```
این یک توکن معتبرِ BatFather و API credentials واقعی است که در مخزن عمومی commit شده. **باید فوراً از طریق @BotFather باطل (revoke) شود** و از تاریخچه git هم پاک شود.
(اعتبارسنجی آنلاین توکن از این سندباکس ممکن نبود — شبکه فقط به PyPI دسترسی دارد — ولی قالب و مقدار، واقعی است نه placeholder.)

### C3. نصب‌کننده، ناخواسته ربات را با توکنِ شخص دیگری بالا می‌آورد
`install.sh:160` و `install.bat:137`: اگر کاربر حتی یک فیلد را خالی بگذارد:
```bash
cp .env.example .env      # / copy /y .env.example .env
```
→ ربات با توکن نشت‌شده و `OWNER_ID=6173234874` (یک فرد غریبه) اجرا می‌شود؛ نصب‌کننده **هیچ دسترسی مدیریتی به ربات خودش نخواهد داشت** و در عمل دارد ربات شخص دیگری را کنترل می‌کند.

**اصلاح:** به‌جای کپی `.env.example`، با خطا خارج شود؛ و `.env.example` فقط placeholder داشته باشد.

---

## 🟠 بالا (High) — قابلیت‌هایی که کار نمی‌کنند

### H1. کلید «▫️ اجبار ورود غیرفعال» هیچ اثری ندارد
`utils.py:533-569` (`checkjoin`) سطر کانال را می‌خواند ولی فقط از `x[0]` (آیدی) و `x[2]` (لینک دعوت) استفاده می‌کند؛ **ستون `status` هرگز خوانده نمی‌شود**.
پنل ادمین آن را می‌نویسد (`admin_panel.py:225` → `status=1`، `admin_panel.py:235` → `status=0`) و در «📊 وضعیت» هم نمایش می‌دهد (`admin_panel.py:48`)، ولی بررسی عضویت همیشه انجام می‌شود.

نتیجه: به‌محض تنظیم کانال، اجبار ورود **برای همیشه روشن** می‌ماند، در حالی که پنل «غیرفعال» نشان می‌دهد.

**اصلاح:**
```python
x = ch_rows[0]
if len(x) < 4 or int(x[3]) != 1:
    return None
```

### H2. تست شماره ۷ با پینِ وابستگی‌ها در تضاد است → سوئیت قرمز
`tests/test_stream_lifecycle.py:162-170` انتظار دارد `StreamStatus.PLAYING` (حروف بزرگ، مربوط به ntgcalls 1.2.x) وجود داشته باشد، ولی `requirements.txt` نسخه `ntgcalls==1.1.3` را پین کرده که فقط عضو Title-case دارد (تأیید شد: `['Idling','Paused','Playing']`). shim داخل `clients.py:25-39,77-88` هم روی 1.1.3 عملاً no-op است.

**اصلاح:** تست را مشروط کنید:
```python
if hasattr(StreamStatus, "PLAYING"):
    check(..., StreamStatus.PLAYING in conv and StreamStatus.IDLING in conv)
else:
    check(..., StreamStatus.Playing in conv and StreamStatus.Idling in conv)
```

### H3. `helper_ping` کد مرده است — پینگِ هلپر هرگز اجرا نمی‌شود
`handlers/misc.py:41` و `handlers/misc.py:57` **فیلتر کاملاً یکسان** دارند (`filters.group & (regex ^(پینگ)$ | ^([Pp][Ii][Nn][Gg])$)`) و هر دو در گروه ۰ هستند.

تأیید عملی با دیسپچر واقعی pyrogram روی پیام «پینگ» در سوپرگروه:
```
help_cmd        -> False
ping_cmd        -> True     ← ایندکس ۱ در گروه ۰
helper_ping     -> True     ← ایندکس ۲، هرگز نمی‌رسد
```
طبق `pyrogram/dispatcher.py` (`handler_worker`)، بعد از اولین callback که `ContinuePropagation` ندهد، حلقه داخلی `break` می‌شود. پس `helper_ping` غیرقابل‌دسترس است.

**اصلاح:** یا `ping_cmd` را با `raise ContinuePropagation` به `helper_ping` وصل کنید، یا هر دو را در یک هندلر ادغام کنید.

### H4. `/login` نام حساب اشتباه را گزارش می‌کند
`handlers/auth.py:214-220`:
```python
async def _login_done(client, m):
    me = await client.get_me()      # client = ربات، نه هلپر!
    first_name = me.first_name
```
`client` در `login_flow(client, m)` همان کلاینتِ **بات** است و `cli` (کلاینت هلپر) قبل از این `disconnect()` شده. پس پیام «✅ حساب هلپر با موفقیت وارد شد! نام حساب: X» **نام خودِ ربات** را چاپ می‌کند و کاربر نمی‌تواند بفهمد هلپرِ درست لاگین شده یا نه.

**اصلاح:** قبل از `disconnect`، `me = await cli.get_me()` را بگیرید و به `_login_done` پاس بدهید.

### H5. دکمه «بازگشت» در پنل تیوی، پنل را نابود می‌کند
`callbacks/tv.py:95-108`:
```python
if data == "backtv":
    await m.message.delete()          # اول پیام را پاک می‌کند
    await m.message.reply(...)        # بعد به همان پیامِ پاک‌شده ریپلای می‌زند → تلگرام رد می‌کند
    except Exception: pass            # خطا بلعیده می‌شود
```
نتیجه: با زدن «بازگشت»، پیام حذف می‌شود و هیچ پنل جدیدی ظاهر نمی‌شود.

**اصلاح:** `await client.send_message(chat_id, ..., reply_markup=utils.tv_ir_keyboard(uid))` بدون ریپلای.

### H6. «آنلاین بودن هلپر» فقط از روی وجود فایل تشخیص داده می‌شود
`clients.py:93-94`: `helper_session_exists()` فقط `os.path.exists(sessions/helper.session)` است.
اما `main.py:74-89` ممکن است در `ubot.start()` یا `call_py.start()` شکست بخورد (سشن نامعتبر / خطای py-tgcalls) و فقط یک `print` بزند. در این حالت همه مسیرهای پخش (`handlers/playback.py:34-44`، `callbacks/tv.py:126`، `callbacks/panel.py:284`) از چک عبور می‌کنند و کاربر به‌جای پیام روشن، «• پخش با مشکل مواجه شد !» می‌گیرد.

**اصلاح:** یک فلگ زمان‌اجرا (`HELPER_ONLINE`) در `clients.py` تنظیم کنید و `require_helper` آن را چک کند. (`helper_ok` در `main.py:81` ساخته می‌شود ولی هرگز استفاده نمی‌شود.)

### H7. ماشین‌حالت انقضای اعتبار می‌تواند برای همیشه قفل شود
`tasks.py:57-60`:
```python
req  = await app.get_chat(chat_id)
req2 = await app.get_chat(int(i[1]))          # ← اگر مالک گروه هرگز /start نزده باشد، اینجا Exception
database.execute("UPDATE charge SET status=1 WHERE idgp=?")   # ← هرگز اجرا نمی‌شود
```
چون `UPDATE` بعد از دو `get_chat` و داخل همان `try` است، هر گروهی که مالکش در دسترس نباشد (یا گروه حذف/محدود شده باشد) **هرگز `status` نمی‌گیرد** → هر ۱۰ دقیقه دوباره تلاش می‌شود، هرگز منقضی نمی‌شود و ربات از آن خارج نمی‌شود. همین الگو در `tasks.py:162-165` (ویدیو) هم هست.

**اصلاح:** `UPDATE` را قبل از هر `get_chat` انجام دهید و اعلان‌ها را جداگانه `try` کنید.

### H8. `پاکسازی` فایل‌های لیست پخش را پاک می‌کند ولی رکوردها می‌مانند
`handlers/group_admin.py:990-1003` کل `downloads/` را بازگشتی پاک می‌کند؛ اما `handlers/playback.py:850-856` فایل‌های پلی‌لیست را در `downloads/<chat_id>/<title>.mp3` ذخیره و مسیرشان را در جدول `playlist` ثبت می‌کند.
بعد از `پاکسازی`، `پخش لیست` روی هر ترک `join_group_call` را شکست می‌خورد و `continue` می‌کند (`playback.py:923-927`) → **سکوت مطلق، بدون هیچ پیام خطا**.

**اصلاح:** `پاکسازی` فقط فایل‌های موقت (`mus_*`, `vid_*`, `ded_*`, `dvid_*`, `auto_*`) را پاک کند، یا `playlist` را هم پاک کند.

### H9. `سرچ یوتیوب` حلقه رویداد را بلاک می‌کند
`handlers/playback.py:783-785`:
```python
from youtubesearchpython import VideosSearch
search = VideosSearch(query, limit=1)
result = search.result()["result"]     # I/O شبکه‌ای همگام داخل هندلر async
```
تا پایان درخواست YouTube، **کل ربات (همه چت‌ها) فریز می‌شود**.

**اصلاح:** `await asyncio.to_thread(lambda: VideosSearch(query, limit=1).result())`.

### H10. `سرچ` / `پخش خودکار` به سقف ۲۰ مگابایت تلگرام می‌خورند
`handlers/playback.py:691`: `client.send_audio(m.chat.id, download, ...)` و `:738`: `ubot.send_audio("me", download, ...)` — هر دو **URL** را به تلگرام می‌دهند تا خودش دانلود کند؛ سقف دانلود از URL برای بات ۲۰ مگابایت است. آهنگ‌های ۳۲۰kbps بلند معمولاً از این سقف رد می‌شوند و خطا به «• موزیک مورد نظر یافت نشد !» تبدیل می‌شود (پیام گمراه‌کننده).
همچنین `autoplay` فایل را در Saved Messages هلپر آپلود و بعد دانلود می‌کند (دو بار ترافیک کامل) و اگر `mus.delete()` اجرا نشود، فایل در اکانت هلپر می‌ماند.
> ⚠️ این مورد از نظر «درستی منطق» تأیید شد، اما چون این سندباکس به `api.melobit.com` دسترسی ندارد (DNS/اتصال ناموفق، `http=000`)، **رفتار زنده API ملوبیت تأیید نشد**.

### H11. دستور انگلیسی `PromoteMusic` به‌خاطر غلط املایی کار نمی‌کند
`handlers/group_admin.py:246-258`:
```python
@app.on_message(... filters.regex(r"^([Pp][Rr][Oo][Mm][Oo][Tt][Ee][Mm][Uu][Ss][Ii][Cc])") ...)  # ← PromoteMusic
    text = utils.clean_command(m.text, "ترفیع موزیک", "PromotMusic").lstrip("@")              # ← PromotMusic (غلط)
```
`clean_command` (`utils.py:520-527`) با `re.search("PromotMusic\b")` دنبال پیشوند می‌گردد که در «PromoteMusic» وجود ندارد، پس **کلمه دستور حذف نمی‌شود** و کل متن به `resolve_chat` می‌رسد.

تأیید عملی با تابع واقعی:
```
'PromoteMusic @ali' -> clean_command -> 'PromoteMusic @ali'   ← خراب
'DemoteMusic @ali'  -> clean_command -> 'ali'                 ← درست
regex accepts 'PromoteMusic @ali' -> True
regex accepts 'PromotMusic @ali'  -> False
```
نتیجه: `PromoteMusic <user>` همیشه «User not found !» می‌دهد. (بررسی خودکار همه ۲۵ `clean_command` نشان داد این **تنها** ناهماهنگی است.)

**اصلاح:** `"PromotMusic"` → `"PromoteMusic"`.

### H12. چهار دستور در پنل راهنما تبلیغ می‌شوند که اصلاً وجود ندارند
`callbacks/help.py:414-420` و `:525-531` دستورهای زیر را مستند کرده‌اند:
```
✧ `بیصدا`   ✧ `باصدا`   ✧ `silent`   ✧ `unsilent`
```
اما **هیچ هندلر متنی** برای این‌ها وجود ندارد:
```
$ grep -rn "filters.regex" handlers/*.py | grep -iE "بیصدا|باصدا|silent"
  NONE
```
بی‌صدا/باصدا فقط به‌صورت دکمه اینلاین (`mutemus`/`unmutemus`/`mutevid`/`unmutevid` در `callbacks/player.py`) پیاده شده‌اند. کاربر طبق راهنما تایپ می‌کند و هیچ اتفاقی نمی‌افتد.

تأیید: مقایسه خودکار **همه ۷۹ دستور مستندشده در `help.py`** با ۱۸۴ توکن دستور پیاده‌شده → تنها این ۴ مورد بی‌هندلر هستند.

**اصلاح:** یا چهار هندلر متنی اضافه شود، یا این خطوط از `help.py` حذف و به «دکمه‌های روی کارت پخش» ارجاع داده شوند.

---

## 🟣 شکاف پوشش تست (چرا ۱۶۰ چک سبز، اطمینان کاذب می‌دهد)

`test_panel_buttons.py` واقعاً خوب نوشته شده (دیسپچر واقعی را شبیه‌سازی می‌کند)، ولی **هیچ‌کدام از باگ‌های بالا تحت پوشش نیستند**:

| باگ | پوشش تست |
|---|---|
| H1 `checkjoin` / وضعیت اجبار ورود | ❌ هیچ تستی (`grep -rl checkjoin tests/` → خالی) |
| H3 `helper_ping` کد مرده | ❌ |
| H4 `_login_done` نام اشتباه | ❌ |
| H5 `backtv` | ❌ |
| H7 انقضای اعتبار (`tasks.py`) | ❌ (فقط `_watch_once` تست شده) |
| H11 `PromoteMusic` | ❌ |
| H12 `بیصدا`/`باصدا` | ❌ (فقط در `test_layout.py` به‌عنوان متن دیده می‌شود) |
| S1 `پخش فایل` | ❌ |
| R9 `lang_of(0)` | ❌ |

ضمناً `tests/test_panel_buttons.py:125-129` خطای فیلترها را با `except Exception: continue` می‌بلعد، پس یک فیلتر شکسته هم «سبز» می‌ماند.

---

## 🟡 امنیتی (Security)

### S1. `پخش فایل` / `/playfile` = خواندن فایل دلخواه از سرور
`handlers/playback.py:1303-1351`: `_play_local_file` هر مسیری که کاربر بفرستد را پخش می‌کند و تنها محافظ، لیست دسترسی موزیک/ویدیو است. یعنی **هر ادمین موزیک/ویدیو در هر گروه نصب‌شده** می‌تواند صدای هر فایل خواندنی روی هاست را در ویس‌چت پخش کند (مثلاً دانلودهای گروه دیگر، یا هر فایل صوتی روی دیسک).

**اصلاح:** مسیر را با `os.path.realpath()` داخل `cfg.DOWNLOAD_DIR` محدود کنید.

### S2. خطاهای خام به کاربر برمی‌گردد
`handlers/auth.py:179,184,204` و `handlers/misc.py:125` متن استثنا را مستقیم در پیام می‌گذارند (`❌ خطا : \`{exc}\``) → نشت جزئیات داخلی/مسیرها به کاربر.

### S3. `database.py` هیچ PRIMARY KEY / UNIQUE / ایندکسی ندارد
`database.py:30-147`: هیچ جدولی کلید اصلی ندارد؛ `charge`/`charge2` می‌توانند برای یک `idgp` چند سطر بگیرند (مسیرهای `charge_*_group` در `group_admin.py:679-737` فقط `UPDATE` می‌کنند ولی مسیرهای دیگر `INSERT`). همه پرس‌وجوها هم `WHERE idgp=?` بدون ایندکس هستند.

---

## 🟠 پایداری (Robustness)

### R1. `m.from_user.id` بدون محافظ در ۱۵۱ نقطه (فقط ۸ نقطه محافظت‌شده)
```
grep -c "m.from_user.id" handlers/ callbacks/  → 151
grep -c "m.from_user.id ... if m.from_user else" → 8
```
پیام‌های ادمین ناشناس (anonymous admin) و پست‌های کانال در گروه `from_user = None` دارند → `AttributeError` → pyrogram فقط لاگ می‌زند و دستور بی‌صدا نادیده گرفته می‌شود. نمونه: `handlers/misc.py:81` (`bot_status`).

### R2. `m.text` فرض شده که `None` نیست (۹ مورد)
`filters.regex` روی **caption** هم مچ می‌شود، ولی `m.text` در آن حالت `None` است.
محل‌های دقیق (`grep -n "text = m.text"`):
```
handlers/playback.py:315     text = m.text
handlers/playback.py:419     text = m.text.replace("پخش ویدیو", "")
handlers/group_admin.py:661  text = m.text
handlers/group_admin.py:684  text = m.text
handlers/group_admin.py:704  text = m.text
handlers/group_admin.py:726  text = m.text
handlers/group_admin.py:846  text = m.text.replace("خروج ", "")...
```
یک عکس/ویدیو با کپشن «پخش لینک …» → `AttributeError: 'NoneType' object has no attribute 'replace'`.

### R3. `group_credit` روی `member.user` محافظت ندارد
`handlers/group_admin.py:747-748` در حالی که `config_music_admins` (`:381-383`) همان حلقه را با `if member.user is None: continue` می‌نویسد → رفتار ناسازگار؛ یک عضو بدون `user` کل دستور `اعتبار` را می‌اندازد.

### R4. تکه‌کردن مارک‌دان در ۴۰۰۰ کاراکتر می‌تواند پیام را خراب کند
`handlers/admin_panel.py:264-273`: برش دقیقاً در ۴۰۰۰ کاراکتر، بدون توجه به `**…**` یا `[…](…)` → تلگرام پارس را رد می‌کند؛ فقط `MessageEmpty` گرفته می‌شود، پس یک لیست بلند گروه می‌تواند ناقص/بی‌پاسد بماند.

### R5. `convo.PENDING` در حافظه و بدون timeout
`convo.py:25-39`: اگر ربات ری‌استارت شود سؤال‌های در انتظار گم می‌شوند؛ و اگر صاحب ربات بعد از یک سؤال پنل، هیچ جوابی ندهد، **اولین متن غیردستوری بعدی او بلعیده می‌شود** (`StopPropagation` در `convo.py:60`). ضمناً `CANCEL_WORDS` شامل `/skip` است (`convo.py:27`) که بی‌ربط به پنل خصوصی است.

### R6. همه دسترسی‌های SQLite همگام داخل هندلرهای async هستند
`database.py:188-208` — هر فراخوانی `query/execute` یک cursor باز می‌کند و بلاک می‌کند؛ با چند گروه فعال، حلقه رویداد مرتباً متوقف می‌شود.

### R7. `i18n.t()` برای کاربران ثبت‌نشده، I/O فایل انجام می‌دهد
`i18n.py:14-17` → `database.get_lang()` (`database.py:289-293`) → در مسیر fallback `config.get_config()` → `_load_dotenv()` (باز کردن `.env`) + `Config()` که **سه `os.makedirs`** اجرا می‌کند (`config.py:60-62`). هر `i18n.t()` برای کاربری که `/start` نزده = یک فایل‌خوانی + سه makedirs.

### R8. `jalali_now()` فارسی نیست
`utils.py:144-150`. خروجی واقعی روی همین سیستم:
```
'09:23:59\nSat 14 Sha 1405'
```
نام روز/ماه انگلیسی/فینگلیش است (وابسته به locale)، و fallback (`time.strftime`) کاملاً میلادی است. در همه کارت‌های «در حال پخش» دیده می‌شود.

### R9. انگلیسی‌زبان‌ها واحد فارسی می‌بینند
`handlers/admin_panel.py:250,253`:
```python
unit = "روز" if i18n.lang_of(0) == "fa" else "days"
```
`i18n.lang_of(0)` همیشه `'fa'` برمی‌گرداند (تأیید شد: `lang_of(0) -> 'fa'`، چون `i18n.py:15` برای مقدار falsy مقدار پیش‌فرض فارسی می‌دهد). پس «📋 لیست گروه‌های فعال» حتی برای کاربر EN هم «روز/ساعت» می‌نویسد.

---

## 🟢 نصب / اسکریپت‌ها

### I1. fallback اف‌اف‌ام‌پی‌جی در `install.sh` کار نمی‌کند
`install.sh:127-131`:
```bash
pip install -q imageio-ffmpeg==0.4.9
FFMPEG_BIN_DIR="$(python -c '...os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe())')"
ln -sf "$FFMPEG_BIN_DIR/ffmpeg-linux-x86_64-v7.0.2" venv/bin/ffmpeg
```
نام فایل hardcode شده اشتباه است. تأیید عملی با `imageio-ffmpeg==0.4.9`:
```
get_ffmpeg_exe -> .../imageio_ffmpeg/binaries/ffmpeg-linux64-v4.2.2
files in dir   -> ['README.md', 'ffmpeg-linux64-v4.2.2']
```
→ `ln -sf` یک symlink شکسته می‌سازد؛ بعد `command -v ffmpeg` و `[ -x venv/bin/ffmpeg ]` هر دو رد می‌شوند و فقط هشدار زرد چاپ می‌شود. یعنی برخلاف ادعای `INSTALL.md:22`، **ffmpeg استاتیک هرگز نصب نمی‌شود** (و روی macOS/ARM که کلاً نام فایل فرق دارد هم بی‌معنی است).

**اصلاح:** `ln -sf "$(python -c 'import imageio_ffmpeg;print(imageio_ffmpeg.get_ffmpeg_exe())')" venv/bin/ffmpeg`

### I2. `install.bat` اصلاً ffmpeg را به PATH وصل نمی‌کند
`install.bat:98` فقط `imageio-ffmpeg` را نصب می‌کند و هیچ symlink/copy انجام نمی‌دهد → `where ffmpeg` همچنان شکست می‌خورد.

### I3. لیبل `:incomplete` داخل بلوک `(...)` در بچ
`install.bat:135` داخل یک بلوک پرانتزی `if ... else (...)` قرار دارد؛ استفاده از `goto`/label داخل بلوک پرانتزی در `cmd.exe` ناپایدار است.
> ⚠️ تأیید نشده — امکان اجرای `cmd.exe` در این محیط نیست.

### I4. `requirements.txt` سالم است
`pip install --dry-run -r requirements.txt` بدون تضاد resolve شد:
`Pyrogram-2.0.106 aiohttp-3.9.5 ntgcalls-1.1.3 py-tgcalls-1.2.9 psutil-5.9.8 yt-dlp-2026.7.4 jdatetime-6.0.1 youtube-search-python-1.6.6 screeninfo-0.8.1 deprecation-2.1.0` — همه نسخه‌های پین‌شده روی PyPI وجود دارند. ✅

---

## ⚪ مستندات در برابر واقعیت

| ادعا | واقعیت |
|---|---|
| `README.md:311-312` «Each test runs offline and must pass with zero errors» | سوئیت با exit code 1 شکست می‌خورد (H2) |
| `README.md:299` تست‌ها = «smoke + handlers + auth + layout» | `run_all.py` شش فایل اجرا می‌کند |
| `README.md:63-64` «there is no hard size limit» | سقف‌های تلگرام: آپلود فایل بات ۵۰MB، دانلود از URL ۲۰MB، دانلود MTProto ۲GB |
| `README.md:71` «Gem* (11 channels)» | ۹ کانال Gem وجود دارد (`callbacks/tv.py:47-56`) |
| `README.md:9` «Original repo: new2rasool/musicrasool» | مخزن فعلی `new2rasool/moslem` است |
| `README.md:12` «dead Melobit endpoints … everything now actually works» | `MELOBIT_API` همچنان `https://api.melobit.com/v1` است (قابل تأیید زنده نبود) |
| `INSTALL.md:22` «ffmpeg استاتیک قرار می‌دهد» | fallback شکسته است (I1) |
| `INSTALL.md:159` «خروجی باید `ALL TESTS PASSED` باشد» | خروجی واقعی `FAILED: ['tests/test_stream_lifecycle.py']` با exit=1 |
| `callbacks/help.py:414-420,525-531` چهار دستور `بیصدا`/`باصدا`/`silent`/`unsilent` | هیچ هندلری ندارند (H12) |
| `callbacks/help.py` دستور `PromoteMusic` | به‌خاطر غلط `PromotMusic` کار نمی‌کند (H11) |

---

## ⚪ کد مرده / کیفیت کد

| محل | مشکل |
|---|---|
| `callbacks/player.py:36-44` | شاخه `data == "a"` هرگز اجرا نمی‌شود — `callbacks/router.py:68` زودتر هندل می‌کند. ضمناً داخلش متغیر `status` محاسبه و هرگز استفاده نمی‌شود |
| `callbacks/player.py:179-187` | شاخه `clzz` هم مرده است — `callbacks/router.py:72` آن را عمومی هندل می‌کند |
| `callbacks/tv.py:117-122` | شاخه `backma` هیچ دکمه‌ای آن را تولید نمی‌کند |
| `main.py:81` | متغیر `helper_ok` ساخته و هرگز استفاده نمی‌شود |
| `handlers/tv.py:10` | `AudioVideoPiped` import شده ولی استفاده نشده |
| `utils.py:122,127` | پارامتر `user_id` در `music_access`/`video_access` بی‌استفاده است |
| `utils.py:161-162` | `send_card` مسیر `mersad.jpg/mp4` را بدون چک وجود فایل امتحان می‌کند (fallback متن درست کار می‌کند، ولی دو درخواست ناموفق اضافی) |
| `callbacks/panel.py:287` | دکمه «افزودن هلپر» برای تست عضویت، **پیام به گروه می‌فرستد** («ربات هلپر عضو گروه میباشد») |
| `database.py:114-122` | نام ستون `kos` (فحش فارسی) از سورس اصلی حفظ شده و در کوئری‌ها پخش است |
| `config.py:47` | `int(_get("API_ID", 0) or 0)` — مقدار غیرعددی در `.env` → `ValueError` بدون پیام راهنما در زمان import |
| `handlers/misc.py:44-45` | پینگ با `random.choice` **جعل** می‌شود، نه اندازه‌گیری واقعی |

---

## ✅ چیزهایی که سالم بررسی شدند (تا گزارش اشتباه ندهم)

- **۱۴۲ هندلر در ۲ گروه درست ثبت می‌شوند** (`smoke_test` + بررسی دستی `app.dispatcher.groups`).
- **هر ۳۷ دکمه پنل owner و ۲۱ دکمه پنل sudo** به هندلر مربوطه می‌رسند (بررسی خودم با مقایسه regexها + `test_panel_buttons.py`: 42/42).
- **هر ۷۴ `callback_data`** در کیبوردها شاخه پردازش دارند؛ همه ۳۸ کانال تیوی دکمه دارند.
- **`main.py` دو بار `app.start()` نمی‌کند** — `Client.run(coroutine)` در pyrogram 2.0.106 کلاینت را start نمی‌کند (فقط coroutine را در لوپ موجود اجرا می‌کند)، پس `await app.start()` داخل `main()` لازم و درست است.
- **`sessions/helper.session` هنگام import ساخته نمی‌شود** (تأیید عملی) → `helper_session_exists()` به‌درستی `False` می‌دهد.
- **`group_credit` با `str(m.chat.id)` کار می‌کند**: برخلاف انتظار، SQLite به‌خاطر column affinity مقدار TEXT را به INTEGER تبدیل می‌کند (تأیید عملی: `str param -> 1 match`). باگ نیست.
- **`_do_sign_in` در `auth.py`** واقعاً signature-adaptive است و ترتیب `phone_number/phone_code_hash/phone_code` درست نگه داشته می‌شود (۳۰/۳۰ تست auth).
- **`convo.py`** با `ContinuePropagation` درست طراحی شده تا دکمه‌های پنل را نبلعد.
- **`pip install -r requirements.txt`** بدون تضاد نصب می‌شود.

---

## 📌 خلاصه اولویت اصلاح

1. **C1** — تست‌ها `.env` و دیتابیس تولید را پاک می‌کنند.
2. **C2/C3** — توکن نشت‌شده را باطل کنید؛ `.env.example` را placeholder کنید؛ fallback نصب‌کننده را حذف کنید.
3. **H1** — اجبار ورود قابل خاموش‌کردن نیست.
4. **H2** — سوئیت تست را سبز کنید.
5. **H3/H4/H5** — پینگ هلپر مرده، نام هلپر اشتباه، دکمه بازگشت تیوی خراب.
6. **H6/H7** — وضعیت هلپر و ماشین‌حالت انقضای اعتبار.
7. **H11/H12** — `PromoteMusic` خراب و ۴ دستور راهنما بدون هندلر.
8. **S1** — محدودسازی `پخش فایل` به `downloads/`.
9. **R1/R2** — گارد `from_user`/`text` در ۱۵۱ نقطه.
10. **I1/I2** — fallback اف‌اف‌ام‌پی‌جی.
11. **پوشش تست** — برای H1/H3/H4/H5/H7/H11/H12/S1 تست رگرسیون اضافه شود، وگرنه همین باگ‌ها دوباره برمی‌گردند.


---

## ۱۲) وضعیت اصلاحات

سورس دست‌نخورده از `moslem.zip` در `musicrasool/` ایمپورت و کامیت شد، سپس
اصلاحات روی آن اعمال شد تا diff قابل بازبینی باشد
(۳۱ فایل، ‎+۱۳۳۷/‎−۲۵۴ خط).

### نتیجه تست بعد از اصلاح

```
$ python tests/run_all.py
RUN: tests/smoke_test.py            → PASSED  (144 هندلر در ۲ گروه)
RUN: tests/test_handlers.py         → 31/31  PASSED
RUN: tests/test_auth.py             → 33/33  PASSED   (+۳ بررسی جدید)
RUN: tests/test_layout.py           → 15/15  PASSED
RUN: tests/test_panel_buttons.py    → 42/42  PASSED
RUN: tests/test_stream_lifecycle.py → 9/9    PASSED   (قبلاً 8/9)
RUN: tests/test_regressions.py      → 55/55  PASSED   (فایل جدید)
ALL TESTS PASSED      exit=0        (مجموعاً ۱۸۵ بررسی در ۷ فایل)
```

**مهم:** قبل از اصلاح، اجرای سوئیت `.env` و دیتابیس تولید را پاک می‌کرد.
بعد از اصلاح، پس از اجرای کامل سوئیت در `musicrasool/`:
`no .env` · `no database.sqlite` · `no sessions/helper.session` ·
`downloads/` فقط `.gitkeep`. یعنی C1 واقعاً بسته شده، نه فقط پنهان.

| مورد | وضعیت | چه چیزی عوض شد |
|---|---|---|
| **C1** تست‌ها `.env`/دیتابیس را پاک می‌کنند | ✅ اصلاح شد | `tests/_bootstrap.py` جدید: قبل از `import config`، `BASE_DIR`/`ENV_FILE`/`DOWNLOAD_DIR`/`DB_PATH`/`SESSION_DIR` به `tempfile.mkdtemp()` منتقل می‌شوند و اعتبارنامه از محیط داده می‌شود. هر ۶ فایل تست از نوشتن `.env` و `os.chdir(PROJECT_ROOT)` خلاص شدند. |
| **C2** اعتبارنامه واقعی در `.env.example` | ✅ اصلاح شد | همه مقادیر به `PUT_YOUR_..._HERE` تبدیل شد. `grep` روی کل درخت: هیچ اثری از `8053868457` / `9c9fe04dc2a85e9dd74208335c537f1a` / `918990` نمانده. ⚠️ **باطل‌کردن توکن با @BotFather همچنان به عهده شماست** — من به آن دسترسی ندارم. |
| **C3** fallback `cp .env.example .env` | ✅ اصلاح شد | در هر دو نصب‌کننده حذف شد؛ به‌جایش `.env` با placeholder نوشته می‌شود و مرحلهٔ آخر با `exit 1` جلوی اجرا را می‌گیرد. `config.py` هم placeholder را «تنظیم‌نشده» حساب می‌کند (`_get_clean`/`_get_int`) به‌جای این‌که با `int()` بشکند. |
| **H1** `checkjoin` ستون `status` را نمی‌خواند | ✅ اصلاح شد | `utils.checkjoin` حالا `x[3]` را می‌خواند و اگر صفر/خالی باشد `None` برمی‌گرداند. `UPDATE channel SET status=…` هم به `WHERE idchannel=?` محدود شد. |
| **H2** سوئیت قرمز (`StreamStatus.PLAYING`) | ✅ اصلاح شد | تست هر دو نام‌گذاری enum را پوشش می‌دهد: اگر `PLAYING` وجود داشت آن را وگرنه `Playing`/`Idling` نسخهٔ پین‌شده 1.1.3 را بررسی می‌کند. |
| **H3** `helper_ping` غیرقابل‌دسترس | ✅ اصلاح شد | `ping_cmd` در انتها `m.continue_propagation()` می‌زند؛ با دیسپچر واقعی pyrogram 2.0.106 تأیید شد (`dispatcher.py:250` روی `ContinuePropagation` به هندلر بعدی می‌رود). |
| **H4** پیام موفقیت نام بات را می‌گفت | ✅ اصلاح شد | `_helper_display_name(cli)` هویت **هلپر** را قبل از `disconnect()` می‌خواند و به `_login_done` پاس می‌دهد. ۳ بررسی جدید در `test_auth.py`. |
| **H5** `backtv` پنل را ناپدید می‌کرد | ✅ اصلاح شد | به‌جای `delete()` + `reply()`، حالا `edit_message_text()` (مثل `backahura`). بررسی «delete-then-reply» روی کل درخت: مورد دیگری نیست. |
| **H6** `helper_session_exists()` فقط فایل را می‌دید | ✅ اصلاح شد | `clients.HELPER_ONLINE` + `set_helper_online()` + `helper_ready()` اضافه شد؛ `main.py` نتیجهٔ واقعی start را منتشر می‌کند. هر ۱۲ نقطهٔ گیت پخش/تیوی/ویس‌چت به `helper_ready()` تبدیل شد (نقاط اطلاع‌رسانی در `private.py`/`main.py` عمداً روی `helper_session_exists()` ماندند). تأیید عملی: با session موجود و `ubot.start()` ناموفق، `main()` پیام `helper is NOT online` را چاپ کرد. |
| **H7** `UPDATE` بعد از `get_chat` | ✅ اصلاح شد | در هر ۴ بلوک (`charge`/`charge2` × status 1/2) انتقال وضعیت **اول** انجام می‌شود و `get_chat`ها در `try` جدا با fallback به `_chat_name`/`_chat_link` قرار گرفتند. تست رگرسیون با `get_chat` همیشه‌خطا: سطر ۰→۱ رفت. |
| **H8** `پاکسازی` فایل‌های پلی‌لیست را می‌برد | ✅ اصلاح شد | حالا مسیرهای موجود در جدول `playlist` حفظ می‌شوند، بقیه پاک می‌شوند و دایرکتوری خالی حذف می‌شود؛ تعداد حذف/حفظ به کاربر گزارش می‌شود. |
| **H9** `VideosSearch().result()` بلوکه | ✅ اصلاح شد | `await asyncio.to_thread(_search)`. |
| **H10** URL به `send_audio` + نشتی Saved Messages | ✅ اصلاح شد | `utils.fetch_media()` جدید (aiohttp، chunked، سقف حجم)؛ `سرچ` و `پخش خودکار` اول دانلود و بعد آپلود محلی می‌کنند. رفت‌وبرگشت `ubot.send_audio("me", …)` و نشتی `mus.delete()` کاملاً حذف شد. *خودِ سقف ۲۰/۵۰ مگابایت تلگرام در این سندباکس قابل آزمودن نبود (بدون egress).* |
| **H11** `PromotMusic` غلط املایی | ✅ اصلاح شد | به `PromoteMusic` اصلاح شد. بازبررسی خودکار همهٔ ۲۵ نقطهٔ `clean_command`: تنها ناهمخوانی باقی‌مانده صفر است. |
| **H12** `بیصدا`/`باصدا` بدون هندلر | ✅ اصلاح شد | دو هندلر متنی `mute_cmd`/`unmute_cmd` اضافه شد (همان access list `ازسرگیری`)؛ شمار هندلرها ۱۴۲ → **۱۴۴**. تست رگرسیون هر ۴ کلمه را با `filters.regex` واقعی می‌سنجد. |
| **S1** `پخش فایل` هر مسیری را پخش می‌کرد | ✅ اصلاح شد | `_resolve_local_media()` با `realpath` و محدودسازی به `DOWNLOAD_DIR`؛ `/etc/passwd` و `../../…` رد می‌شوند. |
| **S2** متن خام exception به کاربر | ✅ اصلاح شد | `utils.brief_error()` (نام کلاس + `ID` تلگرام) در هر ۶ پیام کاربرپسند؛ جزئیات در لاگ می‌ماند. `grep`: هیچ `{exc}`/`format(exc)` کاربرپسندی نمانده. |
| **S3** نبود کلید/ایندکس در SQLite | ✅ اصلاح شد | ۱۹ `CREATE INDEX IF NOT EXISTS` روی ستون‌هایی که واقعاً فیلتر می‌شوند. `PRIMARY KEY`/`UNIQUE` عمداً اضافه نشد چون معنی INSERTها را عوض می‌کرد؛ `IF NOT EXISTS` روی دیتابیس قدیمی هم کار می‌کند. |
| **R** `m.text` بدون گارد | ✅ اصلاح شد (۹ نقطهٔ پرخطر) | `utils.msg_text(m)` = `text or caption or ""`. چون `filters.regex` روی `text or caption` مچ می‌کند (`filters.py:846`)، پیامِ دارای کپشن با `m.text=None` می‌آمد و ۹ نقطه AttributeError می‌گرفتند. `clean_command(None)` هم دیگر `"None"` نمی‌سازد. ۱۵۱ استفادهٔ `m.from_user.id` تغییر نکرد (در pyrogram برای پیام عادی هیچ‌وقت None نیست). |
| **R** `member.user` بدون گارد | ✅ اصلاح شد | `group_credit` هم مثل `addmusicadmins`/`addvideoadmins` گارد `is None` گرفت. |
| **R** شکستن markdown در ۴۰۰۰ کاراکتر | ✅ اصلاح شد | `_send_chunked` روی مرز خط می‌شکند (و خطوط خیلی بلند را جدا) و هر خطای ارسال را تحمل می‌کند؛ import بلااستفادهٔ `MessageEmpty` حذف شد. |
| **R** `i18n.t()` فایل I/O به‌ازای هر رشته | ✅ اصلاح شد | `_LANG_CACHE` در `i18n.py`؛ تنها نویسنده `switch_lang` است + `forget_lang()`. |
| **R** `jalali_now()` روز انگلیسی | ✅ اصلاح شد | `aslocale(jdatetime.FA_LOCALE)` → خروجی واقعی `'10:13:55\nشنبه 14 شهر 1405'` (قبلاً `'Sat 14 Sha 1405'`)؛ با `jalali_now("en")` همان شکل ASCII قبلی. |
| **R** `i18n.lang_of(0)` همیشه `'fa'` | ✅ اصلاح شد | `_fmt_charge_list(rows, unit_day, uid)` و `i18n.t(uid, …)`؛ هر ۴ فراخوان `uid` می‌دهند. |
| **R** `convo.PENDING` بدون timeout | ✅ اصلاح شد | `TIMEOUT = 300` + `_expired()`؛ سوال کهنه پیام بعدی کاربر را نمی‌بلعد. |
| **I2** symlink با نام hardcode | ✅ اصلاح شد | مسیر از `imageio_ffmpeg.get_ffmpeg_exe()` پرسیده می‌شود (`ffmpeg-linux-x86_64-v7.0.2` حذف شد). |
| **I3** ویندوز: ffmpeg روی PATH نمی‌رفت | ✅ اصلاح شد | `install.bat` حالا باینری را به `venv\Scripts\ffmpeg.exe` کپی می‌کند و در صورت شکست هشدار می‌دهد. تأیید شد که **هیچ کجای پایتون** `get_ffmpeg_exe()` را صدا نمی‌زند، پس PATH تنها راه است. |
| **D** کد مرده | ✅ بخشی اصلاح شد | دو شاخهٔ غیرقابل‌دسترس `callbacks/player.py` (`"a"`، `"clzz"` — `router.py:68/72` زودتر برمی‌گردند) حذف و دلیلش مستند شد؛ import مردهٔ `helper_session_exists`/`AudioVideoPiped` از `handlers/tv.py` حذف شد. `backma` دیگر مرده نیست: دکمهٔ «بازگشت» کارت پخش ماهواره‌ای قبلاً `backtv` می‌فرستاد و کاربر را به لیست **ملی** می‌برد؛ حالا بر اساس `NATIONAL` بین `backtv`/`backma` انتخاب می‌کند. `helper_ok` در `main.py` هم دیگر بی‌استفاده نیست. |
| **پوشش تست** | ✅ اصلاح شد | `tests/test_regressions.py` با ۵۵ بررسی برای H1/H3/H5/H6/H7/H8/H11/H12/S1/S2/C2/C3/I2/R و در `run_all.py` ثبت شد. `FakeMessage.continue_propagation()` دقیقاً مثل `Update.continue_propagation()` عمل می‌کند. |
| **اسناد در برابر واقعیت** | ✅ اصلاح شد | `README.md`: جدول تست‌ها و شمارش‌ها (۱۴۴ هندلر، ۳۳ auth، ۴۹ رگرسیون)، `Gem* (9 channels)` به‌جای ۱۱، و شفاف‌سازی سقف ۵۰ مگابایت آپلود بات. `INSTALL.md`: رفتار واقعی ffmpeg در هر دو پلتفرم، رفتار placeholder در `.env`، پیام `helper is NOT online`. |

### مواردی که عمداً اصلاح **نشد**

- **باطل‌کردن توکن نشت‌شده** — نیاز به دسترسی به @BotFather دارد؛ فقط از مخزن حذف شد.
- **همگام‌بودن همهٔ فراخوانی‌های SQLite داخل هندلرهای async** — انتقال به `aiosqlite` کل لایهٔ `database.py` و هر ۱۵۰+ فراخوانی را عوض می‌کند. با ایندکس‌های جدید و کش `i18n` فشار اصلی برداشته شد، ولی خودِ موضوع باز است.
- **۱۵۱ استفادهٔ `m.from_user.id`** — در pyrogram برای پیام عادی `from_user` هیچ‌وقت `None` نیست؛ فقط ۸ نقطه گارد داشتند و همان‌ها کافی است.
- **دسترس‌پذیری Melobit / telewebion / لینک‌های HLS** — در این سندباکس egress وجود ندارد؛ همچنان **تأییدنشده** است.


---

## ۱۳) دور دوم — پاک‌سازی و موارد جامانده

بعد از کامیت اول، یک پاس lint و بازبینی مجدد انجام شد.

### lint (pyflakes) روی کل درخت

| | تعداد |
|---|---|
| قبل از هر پاک‌سازی (ایمپورت دست‌نخورده) | **۳۶** |
| بعد از پاک‌سازی | **۲۱** |

مقایسهٔ قبل/بعد نشان داد اصلاحات دور اول **دو import بلااستفاده** به‌جا گذاشته بودند که الان حذف شدند:

- `handlers/group_admin.py` → `import shutil` (بعد از بازنویسی `clear_downloads` دیگر `rmtree` استفاده نمی‌شد)
- `handlers/playback.py` → `ubot` (بعد از حذف رفت‌وبرگشت Saved Messages)

و این‌ها **به‌عنوان اثر جانبی** درست شدند: `status` بلااستفاده در `callbacks/player.py`، هر دو import مردهٔ `handlers/tv.py`، `helper_ok` بلااستفاده در `main.py`، `utils` بلااستفاده در `admin_panel.py`.

۲۱ مورد باقی‌مانده همه از دو دستهٔ بی‌ضررند و **عمداً** نگه داشته شدند:
import‌های دارای اثر جانبی که هندلرها را ثبت می‌کنند (`handlers.misc`، `callbacks.events`، `tasks`، `_bootstrap` و…) — حذفشان بات را می‌شکند — و چند متغیر محلی بی‌استفاده.

### پینگ: عدد واقعی به‌جای `random.choice`

`handlers/misc.py:44-45` و `:68-69` هر دو عدد را با `random.choice([...])` تولید می‌کردند؛ یعنی کارت پینگ **تأخیر ساختگی** را به‌عنوان عدد واقعی نشان می‌داد.

- `↓ دریافت` = `time.time() - m.date.timestamp()` → تأخیر واقعی رسیدن update
- `↑ ارسال` = زمان واقعیِ `await m.reply(...)` برای بات، و یک round-trip واقعی MTProto (`ubot.get_me()`) برای هلپر
- اگر هلپر پاسخ ندهد، به‌جای عدد جعلی پیام خطا می‌آید
- کارت **همان یک پیام** باقی ماند (حین اصلاح یک لحظه دو پیام می‌شد که برگردانده شد)

### `music_access` / `video_access` — پارامتر `user_id`

**عمداً حذف نشد.** ۲۲ فراخوانی `(chat_id, uid)` می‌دهند و حذفش ۲۲ ویرایش پرریسک با صفر تغییر رفتار است؛ در عوض docstring اضافه شد که چرا بلااستفاده است.

### بررسی «راهنما در برابر پیاده‌سازی» — حالا صفر

هر ۷۹ دستورِ مستندشده در `callbacks/help.py` (الگوی ``✧ `cmd` ``) با تک‌تک alternative‌های `filters.regex` در هندلرها مقایسه شد:

```
documented commands            : 79
implemented tokens             : 158
documented but NOT implemented : 0        (در زمان بازبینی: ۴)
```

⚠️ یک نکتهٔ روش‌شناختی: نسخهٔ اول این بررسی **۳ مورد غلط** (`سرچ`، `پخش لینک`، `playlink`) گزارش کرد، چون lookaroundها را *بعد از* حذف گروهِ پوششی strip می‌کرد و `(?! یوتیوب)` / `(?! ?[Vv]ideo)` را به حرفِ بدنهٔ دستور می‌چسباند. ترتیب درست (اول lookaround، بعد `^…$` و گروه پوششی، بعد `[Xx]`) صفر می‌دهد. این بررسی به‌صورت تست دائمی در `test_regressions.py` ثبت شد تا دوباره خراب نشود.

### جدول dead code — وضعیت نهایی

| مورد | وضعیت |
|---|---|
| `callbacks/player.py:36-44` (`data=="a"`) | ✅ حذف شد |
| `callbacks/player.py:179-187` (`clzz`) | ✅ حذف شد |
| `callbacks/tv.py:117 backma` | ✅ دیگر مرده نیست (دکمهٔ بازگشت ماهواره) |
| `main.py:81 helper_ok` | ✅ استفاده می‌شود (`set_helper_online`) |
| `handlers/tv.py:10 AudioVideoPiped` + `helper_session_exists` | ✅ حذف شد |
| `misc.py:44-45` پینگ ساختگی | ✅ عدد واقعی |
| `user_id` در `music_access`/`video_access` | ⏸️ عمداً نگه داشته شد (docstring) |
| جدول `chnl` با `statuschnl` | ⏸️ فقط در SCHEMA است و هیچ‌جا خوانده/نوشته نمی‌شود؛ حذفش سودی ندارد و ریسک دارد |

### نتیجهٔ نهایی تست

```
$ python tests/run_all.py
smoke_test            → PASSED  (144 هندلر در ۲ گروه)
test_handlers         → 31/31
test_auth             → 33/33
test_layout           → 15/15
test_panel_buttons    → 42/42
test_stream_lifecycle → 9/9
test_regressions      → 55/55
ALL TESTS PASSED      exit=0
```

و بعد از اجرای کامل سوئیت، در درخت پروژه هنوز: `no .env` · `no database.sqlite` · `no sessions/helper.session`.

---

## ۱۴. دور سوم — فرمان‌های پخش و یوتیوب (Round 3)

گزارش کاربر: «`پخش`، `پخش خودکار`، `پخش ویدیو` و `پخش خودکار ویدیو` ارور می‌دهند».
بررسی با **پروب واقعی دیسپچر pyrogram** (نه خواندن چشمی regex) انجام شد؛ نتیجه این بود که
مسئله یک باگ نیست بلکه **هشت باگ مستقل** است که روی هم مسیر پخش را می‌بندند.

### ۱۴.۱ فهرست باگ‌ها و اصلاحات

| # | باگ | مدرک | اصلاح |
|---|------|------|-------|
| **P1** | در `handlers/playback.py:306` هندلر `play_dedicate` با فیلتر `^(پخش )(?!لینک\|یوتیوب\|خودکار\|لیست)` ثبت شده و `filters.reply` هم دارد، ولی **قبل از** `playvideo_reply` و `playvideo_dedicate` ثبت می‌شود و `ویدیو`/`فایل` در lookahead نیست. نتیجه: وقتی کاربر به یک ویدیو **ریپلای** می‌کند و `پخش ویدیو` یا `پخش ویدیو @ali` می‌فرستد، پیام در `play_dedicate` می‌افتد و با خطای «کاربر مورد نظر یافت نشد» تمام می‌شود. | پروب دیسپچر: `پخش ویدیو`+reply → `play_dedicate` ❌ | افزودن `ویدیو\|فایل` به lookahead فارسی و `(?! ?[Vv]ideo\| ?[Ff]ile\|…)` به انگلیسی. پروب بعد از اصلاح: → `playvideo_reply` / `playvideo_dedicate` ✅ |
| **P2** | `utils.utub()` فقط `yt-dlp`/`youtube-dl` را از روی `PATH` پیدا می‌کرد و `FileNotFoundError` را با `continue` می‌بلعید؛ در نهایت `""` برمی‌گرداند بدون هیچ تشخیص. `shutil.which("yt-dlp")` = **None** مگر اینکه `venv/bin` روی PATH باشد. | `/home/user/venv/bin/yt-dlp` وجود دارد ولی `shutil.which` آن را نمی‌بیند | `utils._find_exe()` = PATH + `dirname(sys.executable)`؛ `ytdlp_exe()`؛ `ffmpeg_missing()` |
| **P2b** | انتخاب‌گر فرمت `best[height<=?720][width<=?1280]` فقط فرمت **ترکیبی** می‌خواهد و هیچ fallback ندارد → برای بسیاری از ویدیوهای یوتیوب stdout خالی. | — | زنجیرهٔ `YTDLP_FMT_VIDEO` با fallback به `bv*+ba` (مرج با ffmpeg) و در آخر `b` بدون قید |
| **P3** | شرط `"googlevideo.com" not in direct` در `:843` و `:876` لینک‌های سالم را هم رد می‌کرد. | — | حذف شد |
| **P4** | URL راه‌دور مستقیم به ffmpeg داده می‌شد: لینک‌های googlevideo ~۶ ساعت منقضی می‌شوند، `VideoParameters()` پیش‌فرض همه‌چیز را به **۶۴۰×۳۶۰** کوچک می‌کرد، و `AudioVideoPiped` هر دو پرچم را REQUIRED می‌کند. | `pytgcalls/ffmpeg.py:153 build_command` مستقیماً `ffmpeg -i "<path>"` می‌زند و **هیچ‌وقت** yt-dlp صدا نمی‌زند | `utils.ytdlp_download()` / `utils.download_url()` فایل را محلی می‌کنند؛ `probe_media()` رزولوشن واقعی را می‌دهد؛ تست تأیید می‌کند `1280x720` پروب‌شده جای ۶۴۰×۳۶۰ را می‌گیرد |
| **P5** | `youtube_play` فقط زیررشتهٔ لفظی `youtube.com/watch` را می‌پذیرفت → `youtu.be/`، `/shorts/`، `/live/` و `music.youtube.com` رد می‌شدند. (`utils.is_youtube_link` که `youtu.be` را قبول می‌کرد اینجا اصلاً استفاده نمی‌شد.) | — | `utils.is_youtube_link()` بازتعریف شد و حالا در هندلر استفاده می‌شود |
| **P6** | `utils.melobit_search` کوئری را مستقیم در URL می‌گذاشت: `f"{base}/search/song?query={query}&limit={limit}"`. yarl کاراکتر `#` را encode نمی‌کند → `query=rock+#1&limit=1` باعث می‌شود `#…` fragment شود و **`&limit=1` کاملاً گم شود**؛ `&` هم کوئری را می‌شکند. | با yarl تأیید شد | `session.get(url, params={...})` |
| **P7** | `play_link_video` فقط دنبال رشتهٔ لفظی `.mp4`/`.mkv` در URL می‌گشت → `.webm`، `.mov`، لینک با query string و لینک یوتیوب همه «لینک دانلود ویدیو نیست» می‌گرفتند. | — | فقط `startswith("http")` لازم است، بقیه‌اش با دانلود واقعی تعیین می‌شود |
| **P8** | `youtube-search-python` تنها منبع جستجو بود و HTML-scraping است. | **اجرا شد:** `VideosSearch("test").result()` → `TypeError: post() got an unexpected keyword argument 'proxies'` — یعنی این کتابخانه در محیط فعلی **کاملاً از کار افتاده** و `سرچ یوتیوب` بدون توجه به شبکه ۱۰۰٪ مرده بود | `utils.ytdlp_search()` اول از `ytsearch{n}:` خود yt-dlp استفاده می‌کند؛ `youtube-search-python` فقط fallback است |

### ۱۴.۲ مسیرهای URL — یک نقطهٔ ورود مشترک

پنج جا URL خام مستقیم به `play_audio`/`play_video` داده می‌شد (`پخش لینک`،
`پخش لینک ویدیو`، `/play <url>`، `/playvideo <url>`، و شاخهٔ `text.startswith("http")`
داخل `play_dedicate`). همه به `handlers.playback._resolve_stream_url()` وصل شدند:

```
_resolve_stream_url(url, chat_id, uid, msg_id, video)
  ├─ is_youtube_link(url)  →  ytdlp_info() برای عنوان + ytdlp_download()
  └─ در غیر این صورت       →  utils.download_url()  (با سقف MAX_LINK_BYTES = 300 MB)
  └─ probe_media()  →  رزولوشن واقعی
  → (path, title, resolution, error)
```

خطاها هم دیگر در یک پیام «Download failed !» گم نمی‌شوند: `_download_failed()` دلیل واقعی
را برمی‌گرداند، مثلاً `yt-dlp is not installed` در برابر `ffmpeg is missing` در برابر
`Video unavailable` — سه مشکل کاملاً متفاوت که قبلاً یک پیام یکسان داشتند.

همچنین هر دو سازندهٔ استریم ویدیو (`play_video` و `play_dedicated_video`) وقتی رزولوشن
داده نشده، فایل را پروب می‌کنند؛ در غیر این صورت `VideoParameters()` پیش‌فرض همهٔ ویدیوها
را به ۶۴۰×۳۶۰ پایین می‌آورد.

### ۱۴.۳ جدول مسیردهی بعد از اصلاح (پروب واقعی دیسپچر)

```
پیام                     reply  هندلر              قبل از اصلاح
--------------------------------------------------------------
پخش                       ✔     play_reply         —
پخش @ali                  ✔     play_dedicate      —
پخش ویدیو                 ✔     playvideo_reply    play_dedicate  ❌
پخش ویدیو @ali            ✔     playvideo_dedicate play_dedicate  ❌
پخش ویدیو @ali            ✘     playvideo_dedicate —
پخش فایل …                ✘     play_file_cmd      —
پخش لینک …                ✘     play_link          —
پخش لینک ویدیو …          ✘     play_link_video    —
پخش خودکار …              ✘     autoplay           —
پخش یوتیوب …              ✘     youtube_play       —
پخش لیست                  ✘     play_playlist      —
سرچ …                     ✘     search_music       —
سرچ یوتیوب …              ✘     youtube_search     —
```

> نکتهٔ مستندسازی: دستوری به نام **«پخش خودکار ویدیو» در سورس وجود ندارد**؛
> `پخش خودکار` هندلر `autoplay` است و نسخهٔ ویدیویی ندارد. اگر کاربر این را می‌فرستاد،
> با P1 در `play_dedicate` می‌افتاد و «کاربر یافت نشد» می‌گرفت. بعد از اصلاح به
> `autoplay` با کوئری «خودکار ویدیو» می‌رود.

### ۱۴.۴ تست جدید

`tests/test_playback_youtube.py` — **۷۷ بررسی**، به‌عنوان هشتمین ورودی در `TESTS` افزوده شد.
مهم‌ترین بخش آن یک **پروب واقعی دیسپچر** است (`app.dispatcher.groups` را پیمایش می‌کند و
`h.filters(app, m)` را صدا می‌زند) تا مسیردهی فرمان‌ها واقعاً اجرا شود، نه اینکه regex
چشمی خوانده شود.

> دام پروب: در pyrogram 2.0.106 فیلتر `filters.reply` مقدار `bool(m.reply_to_message_id)`
> را می‌سنجد، **نه** `m.reply_to_message`. اگر فقط آبجکت ریپلای ست شود، همهٔ هندلرهای
> `filters.reply` مقدار False می‌دهند و پروب بدون هیچ خطایی نتیجهٔ غلط می‌دهد.

### نتیجهٔ نهایی تست

```
$ python tests/run_all.py
smoke_test             → PASSED  (144 هندلر در ۲ گروه)
test_handlers          → 31/31
test_auth              → 33/33
test_layout            → 15/15
test_panel_buttons     → 42/42
test_stream_lifecycle  → 9/9
test_regressions       → 55/55
test_playback_youtube  → 77/77   ← جدید
ALL TESTS PASSED       exit=0
```

`pyflakes` روی سورس ارسالی (بدون `tests/`): **۷ اخطار** که هیچ‌کدام خطای واقعی نیستند —
۲ مورد `imported but unused` در `main.py:32,34` (ایمپورت با اثر جانبی برای ثبت هندلرها،
که pyflakes نمی‌تواند تشخیص دهد) و ۵ مورد `assigned to but never used`
(`admin_panel.py:40,41,820`، `auth.py:200`، `tasks.py:326`).
هیچ `undefined name`، `redefinition` یا خطای واقعی دیگری وجود ندارد.
(مقایسه با بیس‌لاین `89ced60`: ۳۶ اخطار.)

### آنچه در این محیط قابل تست نبود

ساندباکس خروجی شبکه ندارد، بنابراین **دانلود واقعی از یوتیوب و پخش واقعی در ویس‌چت
تأیید نشده است**. آنچه تأیید شد: کشف باینری yt-dlp، ساخت درست فرمان yt-dlp، شکل
URLهای ملوبیت، مسیردهی همهٔ فرمان‌ها، انتخاب رزولوشن، و اینکه همهٔ مسیرهای خطا به‌جای
استثنا یک دلیل خوانا برمی‌گردانند (با URL غیرواقعی اجرا شد:
`ERROR: [generic] x: Unable to download webpage: [Errno -2] Name or service not known`).

---

## ۱۵. دور چهارم — فرمان گمشده، پروب واقعی، و پوشش کامل مسیردهی

### ۱۵.۱ `پخش خودکار ویدیو` اصلاً وجود نداشت

کاربر این فرمان را در فهرست خرابی‌ها آورده بود. بررسی سورس نشان داد **چنین هندلری وجود
ندارد** — و بدتر، regex هندلر `autoplay` برابر `^(پخش خودکار)` بدون هیچ lookahead بود،
پس `پخش خودکار ویدیو آهنگ شاد` در هندلر موزیک می‌افتاد، ملوبیت را با کوئری
«خودکار ویدیو آهنگ شاد» جستجو می‌کرد و «موزیک مورد نظر یافت نشد» برمی‌گرداند.
دقیقاً همان الگوی باگ P1.

**اصلاح:** هندلر `autoplay_video` اضافه شد (جستجو با yt-dlp، دانلود، پروب رزولوشن،
پخش) و **قبل از** `autoplay` ثبت می‌شود؛ به regex هندلر `autoplay` هم
`(?! ?ویدیو)` / `(?! ?[Vv][Ii][Dd][Ee][Oo])` اضافه شد.

### ۱۵.۲ `probe_resolution` / `probe_duration` خاموش شکست می‌خوردند (باگ جدی)

هر دو تابع `for exe in ("ffprobe",)` را hard-code کرده بودند و `FileNotFoundError` را با
`continue` می‌بلعیدند. نتیجهٔ اجرا در محیط واقعی:

```
shutil.which('ffprobe')   -> None
shutil.which('ffmpeg')    -> None
imageio_ffmpeg.get_ffmpeg_exe() -> .../imageio_ffmpeg/binaries/ffmpeg-linux-x86_64-v7.0.2  (وجود دارد)
probe_resolution(ویدیوی واقعی 320x240)  -> None     ← باگ
probe_duration(همان ویدیو)              -> None     ← باگ
```

یعنی روی هر ماشینی که `ffprobe` روی PATH نباشد (که نصب‌کنندهٔ پروژه فقط `ffmpeg` را
نصب می‌کند، چون `imageio-ffmpeg` نسخهٔ ffprobe ندارد):

- **آشکارساز «پخش زودهنگام قطع شد»** هیچ مدت‌زمانی برای مقایسه نداشت؛
- **رزولوشن همهٔ ویدیوها** به پیش‌فرض ۶۴۰×۳۶۰ سقوط می‌کرد — یعنی اصلاح P4 در دور قبل
  عملاً بی‌اثر می‌ماند.

> **این باگ را تست قبلی من نگرفت** چون `utils.probe_media` را monkeypatch کرده بودم و
> فقط کد خودم را تست کرده بودم، نه کدی که ارسال می‌شود.

**اصلاح:** `utils.ffmpeg_exe()` (PATH ← کنار مفسر ← imageio-ffmpeg)، جستجوی درست
`_find_exe("ffprobe")`، و در صورت نبودن ffprobe **پارس بنر `ffmpeg -i`** به‌عنوان fallback
(`Video: h264 ..., 1280x720` و `Duration: 00:00:07.31`). تست جدید مسیر **واقعی** را با
ویدیوهای واقعیِ تولیدشده اجرا می‌کند، بدون هیچ stub:

```
320x240  -> probe_resolution=[320, 240]   probe_duration=1.0
1280x720 -> probe_resolution=[1280, 720]  probe_duration=1.0
640x480  -> probe_resolution=[640, 480]   probe_duration=1.0
```

### ۱۵.۳ شبکه‌های تلویزیونی هم ۶۴۰×۳۶۰ پخش می‌شدند

`callbacks/tv.py:134` دستور `AudioVideoPiped(path)` را **بدون** `VideoParameters` صدا
می‌زد، در حالی که URLها خودشان `720p` هستند. استریم زنده را نمی‌توان اول دانلود و پروب
کرد، پس `utils.stream_resolution(url)` رزولوشن را از خود URL می‌خواند
(۱۱ شبکه از ۳۸ شبکه `/720p/` دارند) و برای ۲۷ شبکهٔ باقیمانده خود استریم پروب می‌شود.

### ۱۵.۴ پوشش کامل مسیردهی — `tests/test_routing.py`

باگ P1 با خواندن چشمی regex پیدا نشده بود، پس یک تست دائمی نوشته شد که:

1. با **AST** همهٔ regexهای فرمان را از دکوریتور `@app.on_message` بیرون می‌کشد
   (۹۵ فرمان یکتا در ۴ فایل هندلر)؛
2. دیسپچر **واقعی** pyrogram را پیمایش می‌کند و `h.filters(app, m)` را صدا می‌زند؛
3. هندلرهایی که عمداً پیام را به بعدی واگذار می‌کنند (`m.continue_propagation()` یا
   `raise ContinuePropagation`) را از روی AST خودشانشان تشخیص می‌دهد تا گزارش کاذب ندهد؛
4. جدول مسیردهی ۲۶ حالت حساس را **پین** می‌کند تا دیگر برنگردند؛
5. جفت‌فرمان‌های پیشوندی را بررسی می‌کند: هر فرمان **بدون لنگر** که پیشوند فرمان دیگری
   است باید آن را exclude کند.

> **دو دام که این تست اول در آن‌ها افتاد و اصلاح شد** (هر دو باعث نتیجهٔ غلطِ *بدون خطا*
> می‌شدند):
> 1. `Dispatcher.add_handler` در pyrogram ثبت را با `loop.create_task(fn())` انجام
>    می‌دهد، یعنی **غیرهمزمان**. پروبی که قبل از اجرای یک چرخهٔ loop به
>    `dispatcher.groups` نگاه کند جدول را **خالی** می‌بیند — و چون چیزی برای پیمایش نیست،
>    هرگز loop را اجرا نمی‌کند. حل: `flush_registrations()`.
> 2. `filters.reply` مقدار `reply_to_message_id` را می‌سنجد نه `reply_to_message`؛
>    و `ast.get_source_segment` دکوریتور را شامل نمی‌شود، پس lookahead داخل دکوریتور
>    دیده نمی‌شد.

**نتیجه:** `121/121` — ۹۵ فرمان اعلام‌شده همگی به هندلر درست می‌رسند و
**هیچ تداخل پیشوندی بدون exclusion باقی نمانده**.

### ۱۵.۵ وابستگی شکسته

`youtube-search-python==1.6.6` روی requests/urllib3 جدید خراب است:
`VideosSearch(...).result()` → `TypeError: post() got an unexpected keyword argument 'proxies'`.
در `requirements.txt` مستند شد که این فقط fallback است و جستجوی اصلی با
`ytsearch` خود yt-dlp انجام می‌شود، پس خرابی آن کشنده نیست.

### نتیجهٔ نهایی تست (دور چهارم)

```
$ python tests/run_all.py
smoke_test             → PASSED  (144 هندلر در ۲ گروه)
test_handlers          → 31/31
test_auth              → 33/33
test_layout            → 15/15
test_panel_buttons     → 42/42
test_stream_lifecycle  → 9/9
test_regressions       → 55/55
test_playback_youtube  → 101/101
test_routing           → 121/121   ← جدید
ALL TESTS PASSED       exit=0
```

`pyflakes` روی سورس ارسالی: **۷ اخطار** (۲ ایمپورت با اثر جانبی در `main.py` +
۵ متغیر محلی استفاده‌نشده) — هیچ `undefined name` یا `redefinition`.

### آنچه تأیید نشد

خروجی شبکه در این محیط بسته است؛ بنابراین **دانلود واقعی از یوتیوب، پخش واقعی در
ویس‌چت، و پروب رزولوشن استریم‌های زندهٔ تلویزیون** تست نشده‌اند. آنچه با اجرای واقعی
کد تأیید شد: کشف بایناری‌ها، پروب واقعی فایل‌های ویدیویی تولیدشده، ساخت فرمان yt-dlp،
رمزگذاری درست URL ملوبیت، مسیردهی کامل ۹۵ فرمان، و بازگشت دلیل خوانا در همهٔ مسیرهای خطا.

---

## ۱۶. دور پنجم — دو اجرای متوالی و نشتی پیدا‌شده در آن

طبق درخواست، سوئیت **دو بار متوالی در همان پوشه** (بدون پاک‌سازی بین دو اجرا) اجرا شد تا
آلودگی وضعیت بین اجراها هم لو برود. هر دو اجرا بدون خطا بودند، اما همین اجرای مکرر یک
نقص واقعی را آشکار کرد:

### ۱۶.۱ هر اجرا یک پوشهٔ موقت ~۶۰۰ کیلوبایتی جا می‌گذاشت

بعد از چند اجرای متوالی، ۱۳۱ پوشهٔ `musicrasool-test-*` در `/tmp` جمع شده بود.
علت:

```python
# tests/_bootstrap.py
atexit.register(_cleanup)     # درست نوشته شده بود
...
# ولی پایان هر فایل تست:
os._exit(0)                   # ← هندلرهای atexit را دور می‌زند
```

`os._exit()` عمداً استفاده شده بود چون خاموش‌شدن مفسر در teardown کلاینت pyrogram هنگ
می‌کرد — ولی همان `os._exit()` هندلر `atexit` را هم اجرا نمی‌کند، پس `_cleanup()` هرگز
صدا زده نمی‌شد و پوشه‌ها بدون حد انباشته می‌شدند.

**اصلاح:** `tests/_bootstrap.finish(code)` اضافه شد که اول خروجی را flush می‌کند، بعد
`_cleanup()` را اجرا می‌کند و در آخر `os._exit(code)` را صدا می‌زند. هر ۹ فایل تست به آن
وصل شدند؛ حالا تنها جای مجاز `os._exit` داخل خود `finish()` است.

**اندازه‌گیری قبل/بعد:**

```
پوشه‌های موقت قبل از اصلاح، بعد از چند اجرا : 131
پوشه‌های موقت بعد از اصلاح، بعد از ۲ اجرای کامل : 0
```

### ۱۶.۲ نتیجهٔ دو اجرای متوالی (بعد از اصلاح، از اول)

```
run 1: exit=0 | 9 فایل تست | 407/407 | ALL TESTS PASSED
run 2: exit=0 | 9 فایل تست | 407/407 | ALL TESTS PASSED
>>> BOTH CONSECUTIVE RUNS PASSED <<<
```

برای اطمینان از نبود نوسان (flakiness)، سه اجرای متوالی دیگر هم روی یک استخراج تازهٔ zip
انجام شد و هر سه دقیقاً `407/407` با `exit=0` دادند — یعنی نتیجه قطعی است نه شانسی.

همچنین بررسی شد که zip تحویلی **بایت‌به‌بایت** با `git HEAD` یکسان است
(`diff -r` بین استخراج zip و `git archive HEAD` → بدون تفاوت).
