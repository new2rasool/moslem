"""تست‌های ابزار لایهٔ نمایش — handlers/base.py"""

from bot.domain.roles import AccessLevel
from bot.handlers.base import check_access, denied_text


def test_check_access():
    assert check_access(AccessLevel.ADMIN, AccessLevel.ADMIN)
    assert check_access(AccessLevel.SUDO, AccessLevel.OWNER)
    assert not check_access(AccessLevel.MOD, AccessLevel.ADMIN)


def test_denied_text_fa(translator):
    text = denied_text(translator, "fa", AccessLevel.ADMIN)
    assert "ادمین ربات" in text and "⛔" in text


def test_denied_text_en(translator):
    text = denied_text(translator, "en", AccessLevel.SUDO)
    assert "Bot owner / Sudo" in text
