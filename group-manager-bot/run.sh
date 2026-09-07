#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════
# group-manager-bot — اجراکننده / launcher (FA + EN)
#
# فایل .env را (اگر هست) بارگذاری می‌کند و ربات را با همان محیط اجرا
# می‌کند. کاربرد / usage:
#   ./run.sh --check              بررسی سلامت (بدون تلگرام)
#   ./run.sh --run                اجرای زندهٔ تلگرام
#   ./run.sh --run --watch        اجرا + هات‌ری‌لود خودکار پلاگین‌ها
# ═══════════════════════════════════════════════════════════════════════
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .env ]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
fi

exec ./.venv/bin/python -m bot.main "$@"
