"""
Central callback router. Preserves the original behavior of a single
callback handler: public callbacks first, then an access check, then
routing to panel / player / tv / help handlers.
"""
import config
import database
import i18n
from pyrogram.types import CallbackQuery

from clients import app
from . import help as help_cb, panel as panel_cb, player as player_cb, tv as tv_cb

cfg = config.get_config()
OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID


@app.on_callback_query()
async def callback(client, m: CallbackQuery):
    uid = m.from_user.id
    data = m.data or ""

    # ------------------------------------------------------------------
    # Public callbacks (no access check needed)
    # ------------------------------------------------------------------
    if data == "aboutus":
        info = database.info() or {}
        await m.edit_message_text(
            info.get("about") or "ABOUT",
            reply_markup=InlineBackMarkup(),
        )
        return

    if data == "back":
        info = database.info() or {}
        start = info.get("start") or "START"
        if "MENTION" in start:
            start = start.replace("MENTION", m.from_user.mention(m.from_user.first_name))
        if "BOLD" in start:
            start = start.replace("BOLD", "**")
        if "USERID" in start:
            start = str(start).replace("USERID", str(m.from_user.id))
        ch_rows = database.channel()
        channel_link = ch_rows[0][2] if ch_rows else "https://t.me/fnvhfdmnfhjkc"
        await m.edit_message_text(start, reply_markup=_start_markup(uid, info, channel_link))
        return

    if data == "choose_lang":
        await m.edit_message_text(
            i18n.t(uid, "• لطفا زبان مورد نظر خود را انتخاب کنید :", "• Please choose your language :"),
            reply_markup=i18n.language_keyboard(uid),
        )
        return

    if data == "lang_fa":
        i18n.switch_lang(uid, "fa")
        await m.answer("🇮🇷 زبان فارسی فعال شد !", show_alert=True)
        await _refresh_start(client, m)
        return

    if data == "lang_en":
        i18n.switch_lang(uid, "en")
        await m.answer("🇺🇸 English language activated !", show_alert=True)
        await _refresh_start(client, m)
        return

    if data == "a":
        await m.answer(i18n.t(uid, "• در حال پخش ...", "• Now playing ..."))
        return

    if data == "clzz":
        # close button of the language panel - works for everyone
        try:
            await m.message.delete()
        except Exception:
            pass
        await m.answer(i18n.t(uid, "• پنل با موفقیت بسته شد !", "• The panel was closed successfully !"), show_alert=True)
        return

    # ------------------------------------------------------------------
    # Access check (identical to the original bot)
    # ------------------------------------------------------------------
    chat_id = m.message.chat.id if m.message else 0
    allowed = [
        OWNER, SUDO,
        *database.idsudos(),
        *database.idowner(),
        *database.idmusic(chat_id),
        *database.idvideo(chat_id),
        *database.allmusic(),
        *database.allvideo(),
        *database.creators(chat_id),
    ]
    if uid not in allowed:
        return await m.answer(i18n.t(uid, "شما درخواست ندادی ! :)", "You have no request here ! :)"), show_alert=True)

    # ------------------------------------------------------------------
    # Route
    # ------------------------------------------------------------------
    handled = await panel_cb.handle_panel(client, m, data)
    if handled:
        return
    handled = await player_cb.handle_player(client, m, data)
    if handled:
        return
    handled = await tv_cb.handle_tv(client, m, data)
    if handled:
        return
    handled = await help_cb.handle_help(client, m, data)
    if handled:
        return
    await m.answer()


def InlineBackMarkup():
    from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.t(0, "بازگشت 🔙", "Back 🔙"), callback_data="back")]]
    )


def _start_markup(uid, info, channel_link):
    import utils
    return utils.start_keyboard(uid, info, channel_link)


async def _refresh_start(client, m: CallbackQuery):
    """Re-render the start message after a language switch."""
    info = database.info() or {}
    ch_rows = database.channel()
    channel_link = ch_rows[0][2] if ch_rows else "https://t.me/fnvhfdmnfhjkc"
    start = info.get("start") or "START"
    if "MENTION" in start:
        start = start.replace("MENTION", m.from_user.mention(m.from_user.first_name))
    if "BOLD" in start:
        start = start.replace("BOLD", "**")
    if "USERID" in start:
        start = str(start).replace("USERID", str(m.from_user.id))
    try:
        await m.edit_message_text(start, reply_markup=_start_markup(m.from_user.id, info, channel_link))
    except Exception:
        pass
