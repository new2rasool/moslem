"""لایهٔ کش — اینترفیس + پیاده‌سازی درون‌حافظه با TTL (افق ۱)."""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Cache(ABC, Generic[T]):
    @abstractmethod
    def get(self, key: str) -> T | None: ...

    @abstractmethod
    def set(self, key: str, value: T, ttl_s: float) -> None: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def clear(self) -> None: ...


class MemoryCache(Cache[T]):
    """کش سادهٔ درون‌حافظه با انقضای تنبل (lazy expiry) و قفل نخ."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[float, T]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> T | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires, value = item
            if expires <= time.monotonic():
                del self._data[key]
                return None
            return value

    def set(self, key: str, value: T, ttl_s: float) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + ttl_s, value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            self._prune()
            return len(self._data)

    def _prune(self) -> None:
        now = time.monotonic()
        expired = [k for k, (exp, _) in self._data.items() if exp <= now]
        for k in expired:
            del self._data[k]
