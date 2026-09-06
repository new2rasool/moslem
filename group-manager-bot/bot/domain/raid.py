"""
حالت ضد-راید (دامنهٔ خالص) — پنجرهٔ شمارش ورود + وضعیت قفل.

همه‌چیز به زمان تزریقی (`now_fn`) وابسته است تا در تست قطعی باشد.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class RaidWindow:
    """ردیاب ورود عضوها در پنجرهٔ لغزان."""

    limit: int = 5
    window_s: float = 300.0
    lock_s: float = 600.0
    now_fn=time.monotonic
    _joins: list[float] = field(default_factory=list)
    _lock_until: float = 0.0

    def record_join(self) -> bool:
        """
        ثبت یک ورود؛ اگر شمار ورودهای داخل پنجره از حد گذشت و هنوز قفل نیست،
        قفل را فعال می‌کند. خروجی: آیا با این ورود «تازه قفل شد»؟
        """
        now = self.now_fn()
        cutoff = now - self.window_s
        self._joins = [t for t in self._joins if t > cutoff]
        self._joins.append(now)
        if self.locked(now):
            return False
        if len(self._joins) > self.limit:
            self._lock_until = now + self.lock_s
            return True
        return False

    def locked(self, now: float | None = None) -> bool:
        now = now if now is not None else self.now_fn()
        if self._lock_until <= now:
            return False
        return True

    def remaining(self, now: float | None = None) -> float:
        now = now if now is not None else self.now_fn()
        return max(0.0, self._lock_until - now)

    def force_lock(self, seconds: float | None = None) -> None:
        self._lock_until = self.now_fn() + (seconds if seconds is not None else self.lock_s)

    def unlock(self) -> None:
        self._lock_until = 0.0
