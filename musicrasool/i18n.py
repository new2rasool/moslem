"""
MusicRasool - bilingual helpers (Persian / English).

The original bot is Persian-only. This layer keeps the exact Persian
texts as the default (fa) and adds English (en) translations so the
whole UI can be switched per user with /language.
"""
import database

FA = "fa"
EN = "en"

# ----------------------------------------------------------------------
def lang_of(user_id) -> str:
    if not user_id:
        return FA
    return database.get_lang(user_id)


def t(user_id, fa, en=None):
    """Return Persian text by default, English translation for EN users."""
    if en is None:
        en = fa
    if lang_of(user_id) == EN:
        return en
    return fa


def t_lang(lang: str, fa, en=None):
    if en is None:
        en = fa
    return en if lang == EN else fa


def switch_lang(user_id, lang: str):
    database.set_lang(user_id, lang)


# ----------------------------------------------------------------------
# Language picker keyboard
# ----------------------------------------------------------------------
def language_keyboard(uid):
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🇮🇷 فارسی", callback_data="lang_fa"),
                InlineKeyboardButton("🇺🇸 English", callback_data="lang_en"),
            ],
            [
                InlineKeyboardButton(t(uid, "• بستن", "• Close"), callback_data="clzz"),
            ],
        ]
    )
