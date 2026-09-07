"""تست‌های ضد سیل — domain/flood.py (زمان تزریقی برای قطعیت)"""

from bot.domain.flood import FloodTracker


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_flood_under_limit_ok():
    clock = FakeClock()
    tracker = FloodTracker(limit=5, window_s=3.0, now_fn=clock)
    for _ in range(5):
        assert tracker.record("user1") is False  # تا ۵ پیام مجاز


def test_flood_trigger_on_sixth():
    clock = FakeClock()
    tracker = FloodTracker(limit=5, window_s=3.0, now_fn=clock)
    for _ in range(5):
        tracker.record("user1")
    assert tracker.record("user1") is True  # ششمی در پنجره = تخلف


def test_flood_window_expiry_resets():
    clock = FakeClock()
    tracker = FloodTracker(limit=5, window_s=3.0, now_fn=clock)
    for _ in range(5):
        tracker.record("user1")
    clock.advance(3.1)  # پنجره رد شد → سابقه پاک شد
    for _ in range(5):
        assert tracker.record("user1") is False  # دوباره ۵ پیام مجاز
    assert tracker.record("user1") is True  # ششمی دوباره تخلف


def test_flood_per_key_isolation():
    clock = FakeClock()
    tracker = FloodTracker(limit=3, window_s=2.0, now_fn=clock)
    for _ in range(3):
        tracker.record("user_a")  # به مرز رسید
    assert tracker.record("user_b") is False  # کاربر دیگر آزاد است
    tracker.reset("user_a")
    assert tracker.record("user_a") is False  # ریست شد


def test_flood_weighted_media():
    clock = FakeClock()
    tracker = FloodTracker(limit=3, window_s=2.0, now_fn=clock)
    # رسانه وزن ۲ دارد: ۱ + ۲ = ۳ (برابر حد) → هنوز مجاز
    assert tracker.record("u", weight=1.0) is False
    assert tracker.record("u", weight=2.0) is False
    # پیام بعدی از حد می‌گذرد → تخلف
    assert tracker.record("u", weight=1.0) is True


def test_flood_weighted_exact_boundary():
    clock = FakeClock()
    tracker = FloodTracker(limit=3, window_s=2.0, now_fn=clock)
    assert tracker.record("u", weight=3.0) is False  # برابر حد = مجاز
    assert tracker.record("u", weight=0.5) is True  # گذشت از حد


def test_invalid_params():
    try:
        FloodTracker(limit=0)
    except ValueError:
        pass
    else:
        raise AssertionError("limit صفر باید خطا بدهد")
