"""
TV streaming handlers: پخش تیوی / playtv (channel picker) and
توقف تیوی / stoptv.
"""
from pyrogram import filters
from pyrogram.types import Message

import config
import database
import i18n
import utils
from clients import app, call_py

cfg = config.get_config()
OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID


@app.on_message(filters.group & (filters.regex(r"^(پخش تیوی)$") | filters.regex(r"^([Pp][Ll][Aa][Yy][Tt][Vv])$")))
async def play_tv(client, m: Message):
    uid = m.from_user.id
    access = [*database.idsudos(), *database.idowner(), OWNER, SUDO, *database.creators(m.chat.id),
              *database.idvideo(m.chat.id), *database.allvideo()]
    if uid not in access:
        return
    horn = [*database.kir(1), *database.kir(0)]
    if m.chat.id not in horn:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    await m.reply(
        i18n.t(uid, "• لطفا یکی از گزینه های زیر را انتخاب کنید :", "• Please choose one of the options below :"),
        reply_markup=utils.tv_menu_keyboard(uid),
    )


@app.on_message(filters.group & (filters.regex(r"^(توقف تیوی)$") | filters.regex(r"^([Ss][Tt][Oo][Pp][Tt][Vv])$")))
async def stop_tv(client, m: Message):
    uid = m.from_user.id
    access = [*database.idsudos(), *database.idowner(), *database.idvideo(m.chat.id),
              *database.creators(m.chat.id), SUDO, OWNER, *database.allvideo()]
    if uid not in access:
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id in utils.PLAYING:
        utils.clear_streaming(m.chat.id)
        try:
            await call_py.leave_group_call(m.chat.id)
        except Exception:
            pass
        a = utils.jalali_now()
        fa = (
            f"**⌯** **پخش تیوی متوقف شد** **🔇**\n"
            f"**⊹** نام درخواست کننده : {m.from_user.mention(m.from_user.first_name)}\n"
            f"**⊹** شناسه گروه : `{m.chat.id}`\n"
            f"**⊹** ساعت : `{a}` 📅"
        )
        en = (
            f"**⌯** **TV playback stopped** **🔇**\n"
            f"**⊹** Requested by : {m.from_user.mention(m.from_user.first_name)}\n"
            f"**⊹** Group id : `{m.chat.id}`\n"
            f"**⊹** Time : `{a}` 📅"
        )
        await utils.send_card(client, m.chat.id, uid, fa, en, reply_to_message_id=m.id)
