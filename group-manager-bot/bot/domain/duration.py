"""
پارسر مدت‌زمان (دامنهٔ خالص) — «1d6h30m» → 109800 ثانیه.

واحدها: s ثانیه · m دقیقه · h ساعت · d روز · w هفته
- عدد بدون واحد = دقیقه  («90» یعنی ۹۰ دقیقه)
- ترکیب واحدها مجاز است:  «1d 6h 30m»
"""

from __future__ import annotations

import re

UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}

_TOKEN = re.compile(r"(\d+(?:\.\d+)?)([smhdw]?)")

# نمایش کوتاه واحدها برای format_duration
_UNIT_LABEL = {"w": "w", "d": "d", "h": "h", "m": "m", "s": "s"}


class DurationError(ValueError):
    """مدت‌زمان نامعتبر است."""


def parse_duration(raw: str) -> int:
    """
    تبدیل رشتهٔ مدت به ثانیه.

    مثال‌ها: "1d6h30m" → 109800 · "90" → 5400 · "2d" → 172800
    خطا (DurationError) برای رشتهٔ خالی/نامعتبر/صفر.
    """
    text = raw.strip().replace(" ", "").lower()
    if not text:
        raise DurationError("رشتهٔ مدت خالی است")

    seconds = 0.0
    pos = 0
    for match in _TOKEN.finditer(text):
        if match.start() != pos:
            raise DurationError(f"کاراکتر نامعتبر در {raw!r}: بخش {text[pos:match.start()]!r}")
        value = float(match.group(1))
        unit = match.group(2) or "m"  # بدون واحد = دقیقه
        seconds += value * UNIT_SECONDS[unit]
        pos = match.end()

    if pos != len(text):
        raise DurationError(f"کاراکتر نامعتبر در {raw!r}: بخش {text[pos:]!r}")
    total = int(round(seconds))
    if total <= 0:
        raise DurationError("مدت باید بزرگ‌تر از صفر باشد")
    return total


def format_duration(total_seconds: int) -> str:
    """نمایش خوانای مدت — «109800» → «1d 6h 30m»."""
    if total_seconds < 0:
        raise DurationError("مدت منفی قابل نمایش نیست")
    if total_seconds == 0:
        return "0s"

    remaining = total_seconds
    parts: list[str] = []
    for unit in ("w", "d", "h", "m", "s"):
        span = UNIT_SECONDS[unit]
        count, remaining = divmod(remaining, span)
        if count:
            parts.append(f"{count}{unit}")
    return " ".join(parts)
