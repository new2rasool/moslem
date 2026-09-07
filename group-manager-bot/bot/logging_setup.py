"""راه‌اندازی لاگ ساختاریافته (stdlib logging)."""

from __future__ import annotations

import logging
import sys

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    if root.handlers:  # جلوگیری از هندلر تکراری در ری‌استارت
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FMT))
    root.addHandler(handler)
    # کتابخانه‌های پرحرف را خلوت کن
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
