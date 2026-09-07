#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# group-manager-bot — نصب خودکار / Automatic installer (FA + EN)
#
#   ./install.sh            نصب خودکار کامل (اجرا + توسعه: Pyrogram و pytest)
#   ./install.sh --no-dev   فقط وابستگی‌های اجرا (حجم کمتر؛ بدون pytest)
#   ./install.sh --no-check از بررسی سلامت نهایی صرف‌نظر کن
#   ./install.sh --help     راهنما
#
# کارها: ساخت .venv ← نصب پکیج ← ساخت .env از .env.example ← ساخت data/
#        ← بررسی سلامت (python -m bot.main --check)
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"
VENV_DIR=".venv"
EXTRA="run,dev"      # Pyrogram + TgCrypto + pytest (پیش‌فرض کامل)
DEV=0
RUN_CHECK=1

for arg in "$@"; do
    case "$arg" in
        --dev) DEV=1 ;;        # همچنان پذیرفته می‌شود (معادل پیش‌فرض کامل)
        --no-dev) DEV=-1 ;;
        --no-check) RUN_CHECK=0 ;;
        --help|-h)
            echo "کاربرد / Usage:"
            echo "  ./install.sh            نصب خودکار کامل / full auto install"
            echo "  ./install.sh --no-dev   فقط اجرا / runtime only (no pytest)"
            echo "  ./install.sh --no-check بدون بررسی سلامت / skip health check"
            exit 0
            ;;
        *) echo "⚠️  آرگومان ناشناخته / unknown argument: $arg"; exit 2 ;;
    esac
done

say()  { printf '📦 %s\n' "$1"; }
err()  { printf '❌ %s\n' "$1" >&2; }

echo "═══════════════════════════════════════════════"
echo "  group-manager-bot — نصب خودکار / auto install"
echo "═══════════════════════════════════════════════"

# ۱) پایتون ≥ ۳٫۱۰ / Python >= 3.10
say "بررسی پایتون / checking Python ($PYTHON)…"
if ! "$PYTHON" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
    err "پایتون ۳٫۱۰+ پیدا نشد / Python 3.10+ is required."
    err "نصب: Ubuntu/Debian → sudo apt install python3 python3-venv python3-pip"
    exit 1
fi
"$PYTHON" --version

# ۲) محیط مجازی / virtualenv
if [ ! -x "$VENV_DIR/bin/python" ]; then
    say "ساخت محیط مجازی / creating virtualenv in $VENV_DIR …"
    "$PYTHON" -m venv "$VENV_DIR"
else
    say "محیط مجازی موجود است / virtualenv already exists: $VENV_DIR"
fi
PIP="$VENV_DIR/bin/pip"

# ۳) نصب پکیج / install the package
if [ "$DEV" = "-1" ]; then
    EXTRA="run"
    say "نصب فقط وابستگی‌های اجرا / installing runtime extras only…"
else
    say "نصب کامل (اجرا + توسعه) / installing full extras (run+dev)…"
fi
"$PIP" install -q --upgrade pip
"$PIP" install -q -e ".[$EXTRA]"

# ۴) فایل .env / .env file
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        cp .env.example .env
        say "ساخته شد: .env (از روی .env.example) — لطفاً مقادیر واقعی را وارد کنید."
        say "created: .env (from .env.example) — fill in your real values."
    else
        err ".env.example پیدا نشد؛ فایل .env را دستی بسازید / create .env manually."
        err "کلیدها: BOT_TOKEN، API_ID، API_HASH، OWNER_ID"
    fi
else
    say ".env از قبل موجود است / .env already exists (نگه داشته شد / kept)."
fi

# ۵) پوشهٔ داده (sqlite + نشست pyrogram) / data dir
mkdir -p data
say "پوشهٔ data آماده است / data/ directory ready."

# ۶) بررسی سلامت / health check
if [ "$RUN_CHECK" = "1" ]; then
    # بارگذاری .env تا چک با مقادیر واقعیِ کاربر سبز شود / load .env first
    if [ -f .env ]; then
        set -a
        # shellcheck disable=SC1091
        source .env
        set +a
    fi
    say "بررسی سلامت / running health check (python -m bot.main --check)…"
    "$VENV_DIR/bin/python" -m bot.main --check || {
        err "بررسی سلامت خطا داشت. (بعد از تنظیم OWNER_ID در .env دوباره تلاش کنید)"
        err "health check failed — set OWNER_ID in .env and re-run: ./install.sh"
    }
fi

cat <<'SUMMARY'
────────────────────────────────────────────────────────────
✅ نصب کامل شد / Installation finished
   اجرا / run:        ./run.sh --run            (با BOT_TOKEN واقعی)
   اجرا + هات‌ری‌لود / watch: ./run.sh --run --watch
   تست / tests:       .venv/bin/python -m pytest -q
   بررسی / check:     .venv/bin/python -m bot.main --check

   مرحلهٔ بعد / next: 1) ویرایش .env (BOT_TOKEN، API_ID، API_HASH، OWNER_ID)
                     2) ./run.sh --run --watch
────────────────────────────────────────────────────────────
SUMMARY
exit 0
