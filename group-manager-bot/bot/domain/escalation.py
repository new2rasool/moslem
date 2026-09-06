"""موتور تشدید خودکار مجازات (دامنهٔ خالص) — automod.

قواعد (همه روی «ردیف‌های اکشنِ یک هدفِ خاص» در پنجرهٔ اخیر):
    R1: اگر هدف اخیراً ≥ kick_ban بار اخراج (kick/auto:kick) شده و آخرینِ آن‌ها
        اخراج باشد → بن خودکار.
    R2: اگر هدف اخیراً ≥ mute_ban بار سکوت (mute/auto:mute) شده و آخرینِ آن‌ها
        سکوت باشد → بن خودکار.

قواعد توقف:
    - وجود هر ردیف «ban/auto:ban/gban» در پنجره → بدون اقدام (قبلاً بن شده).
    - فقط ردیف‌هایِ «توسط انسان» (by_user>0) شمارش می‌شوند؛ ردیف‌های خودِ ربات
      (by_user=0) شمارش و اقدام نمی‌کنند (جلوگیری از حلقهٔ بی‌نهایت).
"""

from __future__ import annotations

from collections import Counter

STOP_ACTIONS = {"ban", "auto:ban", "gban", "auto:gban"}
KICK_KINDS = {"kick", "auto:kick"}
MUTE_KINDS = {"mute", "auto:mute"}
DEFAULT_WINDOW = 8


def escalate(
    rows: list[dict],
    *,
    target: int,
    kick_ban: int = 2,
    mute_ban: int = 3,
    window: int = DEFAULT_WINDOW,
) -> str | None:
    """
    تصمیم تشدید برای «هدف» بر اساس ردیف‌های اخیر دفتر حسابرسی.

    خروجی: نام اکشن تشدید ('ban') یا None.
    """
    if not rows:
        return None

    recent = rows[:window]
    # توقف: قبلاً بن شده → دیگر تشدید نکن
    for r in recent:
        if r.get("action") in STOP_ACTIONS and (r.get("target_user") or 0) == target:
            return None

    # فقط ردیف‌های همین هدف + اقدام انسانی
    human = [
        r for r in recent
        if (r.get("target_user") or 0) == target and (r.get("by_user") or 0) > 0
    ]
    if not human:
        return None
    latest = human[0]  # recent() جدیدترین‌ها را اول می‌دهد
    latest_action = latest.get("action")

    counts = Counter(human[i].get("action") for i in range(len(human)))
    kicks = counts["kick"] + counts["auto:kick"]
    mutes = counts["mute"] + counts["auto:mute"]

    if kicks >= kick_ban and latest_action in KICK_KINDS:
        return "ban"
    if mutes >= mute_ban and latest_action in MUTE_KINDS:
        return "ban"
    return None
