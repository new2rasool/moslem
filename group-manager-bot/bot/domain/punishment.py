"""
سیاست هشدار و تنبیه پلکانی (دامنهٔ خالص).

زنجیره: هشدار → سکوت موقت → اخراج. وقتی شمار هشدارهای کاربر به سطحی رسید،
یک اکشن خودکار انتخاب می‌شود. همه‌چیز خالص و قابل‌تست است؛ تصمیم نهایی با پلاگین
(و در نهایت آداپتور تلگرام) اجرا می‌شود.
"""

from __future__ import annotations

# ساختار: سطح هشدار → (action, duration_s یا None)
# actionها: "mute", "kick", "ban", "none"
DEFAULT_TIERS: dict[int, tuple[str, int | None]] = {
    3: ("mute", 3600),      # هشدار سوم → سکوت ۱ ساعته
    5: ("mute", 86400),     # هشدار پنجم → سکوت ۱ روزه
    6: ("kick", None),      # هشدار ششم → اخراج
}

DEFAULT_WARN_LIMIT = 3  # آستانهٔ «نمایش خطر» (تعداد هشدار برای اکشن پایه)


class PunishmentPolicy:
    """انتخاب اکشن خودکار بر اساس شمار هشدار."""

    def __init__(self, tiers: dict[int, tuple[str, int | None]] | None = None) -> None:
        self._tiers = dict(tiers or DEFAULT_TIERS)
        # بالاترین سطح اول بررسی می‌شود
        self._sorted = sorted(self._tiers, reverse=True)

    def action_for(self, warn_count: int) -> tuple[str, int | None] | None:
        """اکشن متناظر با شمار هشدار؛ None یعنی هنوز اکشن خودکاری لازم نیست."""
        for level in self._sorted:
            if warn_count >= level:
                return self._tiers[level]
        return None

    def next_level(self, warn_count: int) -> int | None:
        """نزدیک‌ترین سطحِ بالاتر از وضعیت فعلی (برای نمایش «اکشن بعدی»)."""
        for level in sorted(self._tiers):  # صعودی
            if warn_count < level:
                return level
        return None


def default_policy() -> PunishmentPolicy:
    return PunishmentPolicy()
