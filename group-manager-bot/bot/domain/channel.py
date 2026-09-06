"""شناسهٔ کانال (دامنهٔ خالص) — تبدیل مقدار تنظیم «کانال لاگ» به آیدی عددی.

پشتیبانی: «-1001234567890»، «1001234567890» (مثبتِ بدون پیشوند سوپرگروه).
مقادیر غیرعددی مثل «@channel» قابل resolve نیستند → None (فراخواننده تصمیم
می‌گیرد به کجا برگردد؛ الگوی رایج: برگشت به خودِ گروه).
"""

from __future__ import annotations


def parse_channel_id(raw: object) -> int | None:
    """مقدار خام (str/int) → آیدی عددی کانال یا None."""
    ch = str(raw or "").strip()
    if not ch:
        return None
    try:
        return int(ch)
    except (ValueError, TypeError):
        return None
