"""منحنی تجربه/سطح (دامنهٔ خالص).

- امتیاز هر پیام متنی بر اساس طول مفید آن (ضد اسپم: متن‌های خیلی کوتاه ۰).
- سطح L نیاز به «صعودِ پلکانی» دارد: سطح بعد +۱۰۰×سطح فعلی
  (سطح ۲ → +۱۰۰، سطح ۳ → +۲۰۰، سطح ۴ → +۳۰۰ و…).
"""

from __future__ import annotations


def xp_for_level(level: int) -> int:
    """مجموع امتیاز لازم برای «رسیدن به» سطح داده‌شده (سطح ۱ = صفر)."""
    if level <= 1:
        return 0
    # مجموع ۱۰۰×۱ + ۱۰۰×۲ + … تا ۱۰۰×(level-1) = ۵۰×level×(level-1)
    return 50 * level * (level - 1)


def xp_to_next_level(level: int) -> int:
    """امتیاز لازم برای رفتن از این سطح به سطح بعد."""
    return xp_for_level(level + 1) - xp_for_level(level)


def level_from_xp(xp: int) -> int:
    if xp <= 0:
        return 1
    # حل معادلهٔ درجهٔ دوم: ۵۰×L×(L-1) <= xp  →  L = (1+sqrt(1+xp/12.5))/2
    import math

    return int((1 + math.sqrt(1 + xp / 12.5)) / 2)


def progress(xp: int) -> float:
    """پیشرفت به‌سوی سطح بعد (۰ تا ۱)."""
    level = level_from_xp(xp)
    base = xp_for_level(level)
    span = xp_to_next_level(level)
    if span <= 0:
        return 0.0
    return min(1.0, max(0.0, (xp - base) / span))


def xp_gain(text: str) -> int:
    """امتیاز یک پیام متنی: ۵ پایه + ۱ به ازای هر ۸۰ نویسه (حداکثر ۱۵)."""
    length = len(text or "")
    if length < 4:
        return 0
    return min(15, 5 + length // 80)


def xp_gain_media() -> int:
    """امتیاز پیام‌های رسانه‌ای (عکس/ویدیو/…): ثابت و کم."""
    return 3
