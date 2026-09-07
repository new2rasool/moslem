"""پنجره‌های زمانی ارسال (دامنهٔ خالص) — برای محدودیت ساعات پیام.

یک بازه به شکل "HH:MM-HH:MM" می‌تواند از نیمه‌شب بگذرد (مثل ۲۲:۰۰ تا ۰۸:۰۰).
"""

from __future__ import annotations

from datetime import time as dtime


def parse_range(raw: str) -> tuple[dtime, dtime] | None:
    """تبدیل «HH:MM-HH:MM» به (شروع، پایان)؛ ورودی نامعتبر → None."""
    raw = (raw or "").strip().replace(" ", "")
    if "-" not in raw:
        return None
    a, _, b = raw.partition("-")
    try:
        h1, m1 = a.split(":")
        h2, m2 = b.split(":")
        start = dtime(int(h1), int(m1))
        end = dtime(int(h2), int(m2))
    except (ValueError, TypeError):
        return None
    return start, end


def in_window(now: dtime, start: dtime, end: dtime) -> bool:
    """آیا «اکنون» داخل بازه است؟ (بازهٔ گذرنده از نیمه‌شب هم درست کار می‌کند)"""
    if start <= end:
        return start <= now <= end
    # بازهٔ شبانه: مثلاً ۲۲:۰۰ تا ۰۸:۰۰
    return now >= start or now <= end
