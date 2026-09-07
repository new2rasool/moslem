"""
نرمال‌سازی متن (دامنهٔ خالص) — ضد دورزدنِ فیلتر کلمات.

ترفندهای رایج اسپمرها: فاصلهٔ کاذب («قــوانین»)، تکرار حرف («بنننن»)،
حروف عربی به‌جای فارسی («يک كافي»)، نویسهٔ ZWJ/ZWNJ، شکلک‌های کشیده و leet.
"""

from __future__ import annotations

import re
import unicodedata

# یکسان‌سازی حروف عربی ← فارسی (کلید = کاراکتر عربی)
_ARABIC_TO_PERSIAN = str.maketrans(
    {
        "ي": "ی",
        "ى": "ی",
        "ئ": "ی",
        "ك": "ک",
        "ة": "ه",
        "ۀ": "ه",
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ؤ": "و",
        "ء": "",
    }
)

# حرکت‌ها و اعراب عربی + تشدید + کشیدگی (tatweel)
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640\u0653-\u065F]")

# نویسه‌های کنترلی/مخفی Unicode
_CONTROL = re.compile(r"[\u200B-\u200F\u202A-\u202E\u2060\uFEFF]")

# اعداد فارسی/عربی ← لاتین
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# leet سادهٔ لاتین (اختیاری)
_LEET = str.maketrans(
    {"4": "a", "@": "a", "8": "b", "3": "e", "6": "g", "1": "i", "0": "o", "5": "s", "7": "t"}
)

def collapse_repeats(text: str, min_run: int = 3) -> str:
    """
    فشرده‌سازی حروف تکراری پشت‌سرهم («بنننن» → «بن»).

    آستانهٔ پیش‌فرض ۳ است تا حروف دوتاییِ عادی زبان‌ها («hello»، «free»)
    آسیب نبینند؛ اسپمرها معمولاً ۳+ تکرار می‌کنند.
    """
    if min_run < 2:
        raise ValueError("min_run باید حداقل ۲ باشد")
    pattern = re.compile(r"(.)\1{%d,}" % (min_run - 1))
    return pattern.sub(r"\1", text)


def normalize_text(text: str, *, leet: bool = False, collapse: bool = True) -> str:
    """
    نرمال‌سازی کامل برای تطبیق کلیدواژه/فیلتر:

    1. NFKC (یونیکد استاندارد)
    2. یکسان‌سازی عربی→فارسی و اعداد فارسی→لاتین
    3. حذف حرکت/کشیدگی و نویسه‌های کنترلی
    4. حروف لاتین ← کوچک (+ leet اختیاری)
    5. فشرده‌سازی تکرار (اختیاری)
    6. جمع‌کردن فاصله‌ها
    """
    out = unicodedata.normalize("NFKC", text)
    out = out.translate(_ARABIC_TO_PERSIAN)
    out = _DIACRITICS.sub("", out)
    out = _CONTROL.sub("", out)
    out = out.translate(_PERSIAN_DIGITS)
    if leet:
        out = out.translate(_LEET)
    out = out.casefold()
    if collapse:
        out = collapse_repeats(out)
    return " ".join(out.split())
