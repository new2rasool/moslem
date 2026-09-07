"""
ابزارهای لایهٔ نمایش — چک سطح دسترسی به‌صورت خالص (قابل تست بدون تلگرام).

در فاز ۲، دکوریتورهای واقعی روی Pyrogram روی همین توابع سوار می‌شوند.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel, LEVEL_LABELS_EN, LEVEL_LABELS_FA, can
from bot.i18n.loader import Translator


def check_access(actor_level: AccessLevel | int, required: AccessLevel | int) -> bool:
    """آیا actor_level برای required کافی است؟ (نگاه رو به domain.can)"""
    return can(int(actor_level), int(required))


def denied_text(translator: Translator, lang: str, required: AccessLevel) -> str:
    """متن «⛔ دسترسی ندارید» با نام خوانای سطحِ لازم."""
    labels = LEVEL_LABELS_FA if lang == "fa" else LEVEL_LABELS_EN
    return translator.t(lang, "cmd_denied", level=labels.get(required, required.name))
