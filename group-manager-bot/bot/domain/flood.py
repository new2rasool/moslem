"""
ضد سیل — پنجرهٔ لغزان وزنی (دامنهٔ خالص).

مفهوم: هر کلید (کاربر) سابقهٔ «رویدادها + وزن» را در پنجرهٔ زمانی اخیر نگه
می‌دارد؛ اگر جمع وزن در پنجره از آستانه (limit) گذشت، تخلف اعلام می‌شود.

پیاده‌سازی کاملاً وابسته به زمانِ تزریق‌شده (`now_fn`) است تا در تست قطعی باشد.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _Event:
    at: float
    weight: float


class FloodTracker:
    """
    ردیاب ضد سیل برای همهٔ کلیدها (معمولاً user_id یا (chat_id,user_id)).

    نمونه:  limit=5, window_s=3  یعنی حداکثر ۵ پیام در هر ۳ ثانیه؛
    پیام ششمِ داخل پنجره تخلف است (record → True).
    """

    def __init__(self, limit: float = 5, window_s: float = 3.0, now_fn=time.monotonic) -> None:
        if limit <= 0 or window_s <= 0:
            raise ValueError("limit و window_s باید مثبت باشند")
        self.limit = limit
        self.window_s = window_s
        self._now = now_fn
        self._buckets: dict[str, deque[_Event]] = {}

    def record(self, key: str, weight: float = 1.0) -> bool:
        """
        ثبت یک رویداد برای key.

        خروجی: True اگر با این ثبت، جمع وزن در پنجره از آستانه گذشت (تخلف).
        """
        now = self._now()
        bucket = self._buckets.setdefault(key, deque())
        self._prune(bucket, now)
        bucket.append(_Event(at=now, weight=weight))
        total = sum(e.weight for e in bucket)
        return total > self.limit

    def reset(self, key: str) -> None:
        self._buckets.pop(key, None)

    def clear_all(self) -> None:
        self._buckets.clear()

    def _prune(self, bucket: deque[_Event], now: float) -> None:
        cutoff = now - self.window_s
        while bucket and bucket[0].at <= cutoff:
            bucket.popleft()

    def weight_in_window(self, key: str) -> float:
        now = self._now()
        bucket = self._buckets.get(key)
        if not bucket:
            return 0.0
        self._prune(bucket, now)
        return sum(e.weight for e in bucket)
