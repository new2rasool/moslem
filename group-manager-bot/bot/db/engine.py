"""
موتور دیتابیس — مدیریت اتصال‌های SQLite.

هر عملیات یک اتصال مستقل باز می‌کند (ایمن برای asyncio/تست) و با WAL
برای خواندن همزمان بهینه شده است.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_SCHEMA = Path(__file__).parent / "schema.sql"


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        if str(path) == ":memory:":
            raise ValueError("برای حافظهٔ موقت از فایل موقت pytest (tmp_path) استفاده کنید")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path), timeout=15)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self) -> None:
        """اجرای schema.sql (idempotent — با IF NOT EXISTS)."""
        with self.connection() as conn:
            conn.executescript(_SCHEMA.read_text(encoding="utf-8"))
