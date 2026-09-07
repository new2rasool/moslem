"""
بارگذار ترجمه — فایل‌های JSON در bot/i18n/locales/{fa,en}.json.

- کلید گم‌شده در زبان اصلی ← fallback به en ← در نهایت خود کلید.
- قالب‌بندی با {متغیر} پشتیبانی می‌شود (جای‌نگهدار گم‌شده خطا نمی‌دهد).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

LOCALES_DIR = Path(__file__).parent / "locales"
FALLBACK_LANG = "en"
SUPPORTED_LANGS = ("fa", "en")


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


class Translator:
    """کش لوکال‌ها + متد t()."""

    def __init__(self, locales_dir: Path = LOCALES_DIR) -> None:
        self._dir = locales_dir
        self._cache: dict[str, dict[str, str]] = {}

    def load(self, lang: str) -> dict[str, str]:
        if lang in self._cache:
            return self._cache[lang]
        if lang not in SUPPORTED_LANGS:
            lang = FALLBACK_LANG
        path = self._dir / f"{lang}.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        self._cache[lang] = data
        return data

    def available(self) -> list[str]:
        return [p.stem for p in self._dir.glob("*.json") if p.stem in SUPPORTED_LANGS]

    def text(self, lang: str, key: str) -> str:
        """متن خامِ کلید با fallback (بدون قالب‌بندی) — برای استفادهٔ لایه‌های بالاتر."""
        data = self.load(lang)
        if key not in data and lang != FALLBACK_LANG:
            fallback = self.load(FALLBACK_LANG)
            return fallback.get(key, key)
        return data.get(key, key)

    def t(self, lang: str, key: str, **fmt) -> str:
        """متن لوکال با fallback و قالب‌بندی امن."""
        text = self.text(lang, key)
        if fmt:
            return text.format_map(_SafeDict(fmt))
        return text
