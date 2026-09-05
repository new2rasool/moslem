# 📥 راهنمای نصب MusicRasool

این فایل شامل **همه راه‌های نصب** است:

1. نصب خودکار با یک دستور (Linux / macOS)
2. نصب خودکار روی ویندوز
3. نصب دستی (گام‌به‌گام)
4. تنظیم `.env`
5. لاگین حساب هلپر (شماره + کد)

---

## ۱) نصب خودکار — لینوکس / مک (یک دستور)

```bash
cd musicrasool
chmod +x install.sh run.sh
./install.sh
```

اسکریپت به‌صورت خودکار:
- نسخه مناسب پایتون (3.9–3.12) را پیدا می‌کند
- FFmpeg و ابزارهای سیستمی را نصب می‌کند (در صورت نبودن، ffmpeg استاتیک از طریق `imageio-ffmpeg` قرار می‌دهد)
- محیط مجازی `venv` می‌سازد و `requirements.txt` را نصب می‌کند
- فایل `.env` را به‌صورت پرسش‌وپاسخ از شما می‌گیرد (API_ID، API_HASH، BOT_TOKEN، OWNER_ID، SUDO_ID)

سپس اجرا کنید:

```bash
./run.sh
```

---

## ۲) نصب خودکار — ویندوز

پیش‌نیاز: [Python 3.10 (64-bit)](https://www.python.org/downloads/) نصب باشد و گزینه
**“Add Python to PATH”** تیک خورده باشد.

```bat
cd musicrasool
install.bat
```

سپس اجرا:

```bat
run.bat
```

---

## ۳) نصب دستی (گام‌به‌گام)

### ۳.۱ — نصب وابستگی‌های سیستم (FFmpeg و…)

**Ubuntu / Debian:**
```bash
sudo apt update
sudo apt install -y ffmpeg python3.10 python3.10-venv python3-pip git build-essential
```

**CentOS / Rocky / Alma:**
```bash
sudo dnf install -y epel-release ffmpeg python3-pip git gcc-c++
```

**macOS (Homebrew):**
```bash
brew install ffmpeg python@3.10 git
```

**Windows:** FFmpeg از [https://www.gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/)
(نسخه release-full) دانلود و به PATH اضافه کنید، یا اجازه دهید `install.bat` نسخه استاتیک را نصب کند.

### ۳.۲ — محیط پایتون

```bash
cd musicrasool

# ساخت محیط مجازی
python3.10 -m venv venv

# فعال‌سازی
source venv/bin/activate        # لینوکس / مک
:: venv\Scripts\activate.bat    # ویندوز

# ارتقای ابزارها
python -m pip install --upgrade pip wheel setuptools

# نصب وابستگی‌ها (نسخه‌های دقیق)
pip install -r requirements.txt
```

### ۳.۳ — ساخت فایل پیکربندی

```bash
cp .env.example .env
nano .env    # یا هر ویرایشگری
```

| متغیر | توضیح | از کجا |
|---|---|---|
| `API_ID` | شناسه اپلیکیشن | https://my.telegram.org |
| `API_HASH` | هش اپلیکیشن | https://my.telegram.org |
| `BOT_TOKEN` | توکن ربات | https://t.me/BotFather |
| `OWNER_ID` | آیدی عددی شما | https://t.me/userinfobot |
| `SUDO_ID` | آیدی مدیر دوم (میتواند = OWNER_ID) | https://t.me/userinfobot |
| `DEFAULT_LANG` | `fa` یا `en` | — |

> اگر `.env` وجود نداشته باشد، در اولین اجرای ربات، یک **ویزارد تعاملی** همان مقادیر را می‌پرسد.

### ۳.۴ — اجرای ربات

```bash
python run.py
```

---

## ۴) لاگین حساب هلپر (شماره تلفن + کد ورود)

هلپر یک **حساب یوزربات** است که به ویس‌کال می‌پیوندد و موزیک/ویدیو را پخش می‌کند.

1. در چت خصوصی ربات دستور زیر را بفرستید:

   ```
   /login
   ```

2. **شماره تلفن** هلپر را با کد کشور وارد کنید:

   ```
   +989123456789
   ```

3. **کد ورود** ارسال‌شده به آن شماره/تلگرام را وارد کنید.

4. اگر حساب رمز دومرحله‌ای دارد، **رمز عبور** را وارد کنید.

5. دستور زیر را بفرستید تا ربات با نشست هلپر ری‌استارت شود:

   ```
   /restart
   ```

6. حساب هلپر را به گروه(های) خود اضافه کنید (یا از دکمه «افزودن هلپر» در پنل نصب استفاده کنید) و شروع به پخش کنید.

---

## ۵) بررسی نصب — تست‌ها

برای اطمینان از سلامت کامل سورس، همه تست‌ها را اجرا کنید (آفلاین، بدون نیاز به اینترنت):

```bash
python tests/run_all.py
```

خروجی باید `ALL TESTS PASSED` باشد.

---

## ⚠️ نکات مهم

- **نسخه پایتون:** 3.9 تا 3.12 توصیه می‌شود (ویلِ prebuilt برای `ntgcalls`). روی 3.13+ ممکن است نیاز به کامپایل باشد.
- **FFmpeg حتماً لازم است** — اگر نصب نشود پخش صوتی/تصویری کار نمی‌کند.
- توکن و نشست هلپر (`sessions/helper.session`) را محرمانه نگه دارید.
- برای مشکل در نصب `ntgcalls`، بررسی کنید پایتون 64-bit دارید و `pip` به‌روز است.
