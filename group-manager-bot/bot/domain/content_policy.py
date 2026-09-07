"""
سیاست محتوا (دامنهٔ خالص) — تشخیص تخلف قفل‌ها (لینک/فوروارد/رسانه).

خالص و بدون وابستگی: ورودی = نوع/محتوای پیام + تنظیمات قفل‌ها،
خروجی = نام موردِ نقض‌شده یا None.
"""

from __future__ import annotations

import re

# URLهای رایج (https، www، t.me، telegram.me و…)
URL_RE = re.compile(
    r"(?i)\b((?:https?://|www\.|t\.me/|telegram\.me/|tlgrm\.eu/|telegra\.ph/)[^\s<>\"']+)"
)
DOMAIN_RE = re.compile(r"(?i)\b([a-z0-9][a-z0-9.-]*\.[a-z]{2,})\b")

# نگاشت content_type پیام ← نام آیتم قابل قفل
CONTENT_MAP = {
    "photo": "photos",
    "video": "videos",
    "animation": "gifs",
    "sticker": "stickers",
    "voice": "voice",
    "video_note": "video_note",
    "document": "documents",
    "contact": "contacts",
    "location": "locations",
    "poll": "polls",
    "game": "games",
    "text": "text",
}

# نام‌های قفلِ قابل استفاده در دستور (برای اعتبارسنجی)
LOCKABLE = {
    "url",
    "forward",
    "photos",
    "videos",
    "gifs",
    "stickers",
    "voice",
    "video_note",
    "documents",
    "contacts",
    "locations",
    "polls",
    "games",
}

# حالت‌های رفتار هر قفل
VALID_ACTIONS = {"delete", "warn", "notify"}


def has_url(text: str) -> bool:
    """آیا متن شامل لینک است؟"""
    return bool(text and URL_RE.search(text))


def extract_domains(text: str) -> set[str]:
    """دامنه‌های موجود در متن (برای چک لیست سفید)."""
    return {m.group(1).lower() for m in DOMAIN_RE.finditer(text)}


def is_whitelisted(text: str, whitelist: list[str]) -> bool:
    """اگر همهٔ لینک‌های متن داخل لیست سفید باشند True (فقط وقتی url هست)."""
    if not whitelist:
        return False
    allowed = {d.lower().lstrip(".") for d in whitelist}
    domains = extract_domains(text)
    if not domains:
        return False
    return all(d in allowed or any(d.endswith("." + a) for a in allowed) for d in domains)


def check_message(
    *,
    content_type: str,
    text: str = "",
    is_forward: bool = False,
    locks: dict[str, str],
    url_whitelist: list[str] | None = None,
) -> str | None:
    """
    بررسی پیام در برابر قفل‌های فعال گروه.

    خروجی: نام آیتمِ نقض‌شده (اولین برخورد با اولویت url ← forward ← رسانه) یا None.
    locks: {item: action} — فقط مواردی که action آن‌ها چیزی غیر از "" است اعمال می‌شود.
    """
    effective = {k: v for k, v in locks.items() if v in VALID_ACTIONS}
    if not effective:
        return None

    # ۱) لینک (با احترام به لیست سفید)
    if "url" in effective:
        has = has_url(text)
        if has and not is_whitelisted(text, url_whitelist or []):
            return "url"
        # اگر همهٔ لینک‌ها سفید بودند ولی متن فوروارد هم هست… بعداً بررسی می‌شود

    # ۲) فوروارد
    if "forward" in effective and is_forward:
        return "forward"

    # ۳) نوع رسانه
    item = CONTENT_MAP.get(content_type or "")
    if item and item in effective:
        # متنِ ساده تحت قفل text قرار نمی‌گیرد (چون تقریباً همه‌چیز text است)
        if item == "text":
            return None
        return item

    return None
