"""تست‌های کش TTL — cache/cache.py"""

import time

from bot.cache.cache import MemoryCache


def test_set_get():
    cache: MemoryCache[str] = MemoryCache()
    assert cache.get("k") is None
    cache.set("k", "v", ttl_s=60)
    assert cache.get("k") == "v"


def test_expiry():
    cache = MemoryCache()
    cache.set("k", "v", ttl_s=0.05)
    assert cache.get("k") == "v"
    time.sleep(0.1)
    assert cache.get("k") is None


def test_delete_and_clear():
    cache = MemoryCache()
    cache.set("a", "1", ttl_s=60)
    cache.set("b", "2", ttl_s=60)
    cache.delete("a")
    assert cache.get("a") is None and cache.get("b") == "2"
    cache.clear()
    assert cache.get("b") is None


def test_len_prunes_expired():
    cache = MemoryCache()
    cache.set("a", "1", ttl_s=-1)  # از قبل منقضی
    cache.set("b", "2", ttl_s=60)
    assert len(cache) == 1  # len با prune فقط b را می‌شمرد
