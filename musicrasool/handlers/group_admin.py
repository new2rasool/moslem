"""
Group admin commands: install, charge, credit, id, leave, ban,
music/video admin management (add/remove/promote/demote/config/list),
creator (owner) management, global music/video admins, force-join
exemptions and group call creation.
"""
import os
import time

from pyrogram import enums, filters
from pyrogram.types import Message

import config
import database
import i18n
import utils
from clients import app

cfg = config.get_config()
OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID


def _sudo(user_id):
    return user_id in (OWNER, SUDO, *database.idsudos(), *database.idowner())


def _creator(chat_id, user_id):
    return user_id in (OWNER, SUDO, *database.idsudos(), *database.idowner(), *database.creators(chat_id))


# ----------------------------------------------------------------------
# نصب / install -> panel
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^([Ii][Nn][Ss][Tt][Aa][Ll][Ll])$") | filters.regex(r"^(نصب)$")))
async def install_panel(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner()):
        return
    await m.reply(
        i18n.t(uid, "• یکی از گزینه های زیر را انتخاب کنید :", "• Choose one of the options below :"),
        reply_markup=utils.install_keyboard(uid),
    )


# ----------------------------------------------------------------------
# حذف / delete -> delete panel
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(حذف)$") | filters.regex(r"^([Dd][Ee][Ll][Ee][Tt][Ee])$")))
async def delete_panel(client, m: Message):
    uid = m.from_user.id
    horn = [*database.moz(1), *database.moz(0), *database.kir(0), *database.kir(1)]
    if m.chat.id not in horn:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner()):
        return
    await m.reply(
        i18n.t(uid, "• لطفا یکی از گزینه های زیر را انتخاب کنید :", "• Please choose one of the options below :"),
        reply_markup=utils.delete_keyboard(uid),
    )


# ----------------------------------------------------------------------
# نصب موزیک / addmusic
# ----------------------------------------------------------------------
async def _add_music(client, m: Message, chat_id):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    x = database.query("SELECT * FROM gp WHERE status=0")
    installed = [int(i[1]) for i in x]

    if not x:
        req = await client.get_chat(chat_id)
        if req.invite_link is None:
            return await m.reply(i18n.t(uid, "**⌯** لطفا ربات را در گروه فول ادمین کرده و مجددا تلاش کنید **!**", "**⌯** Please make the bot full admin in the group and try again **!**"))
        database.execute("INSERT INTO gp(namegp, idgp, linkgp, status) VALUES(?,?,?,?)", (req.title, req.id, req.invite_link, 0))
        await m.reply(i18n.t(uid, "**⌯** گروه به لیست موزیک اضافه شد !", "**⌯** Group added to the music list !"))
        return

    if int(chat_id) in installed:
        return await m.reply(i18n.t(uid, "**⌯** این گروه از قبل نصب شده است **!**", "**⌯** This group is already installed **!**"))

    limit_rows = database.query("SELECT status,count FROM limmit")
    if limit_rows:
        limitstatus, limitcount = limit_rows[0][0], limit_rows[0][1]
        if limitstatus == 1 and len(x) > limitcount:
            return await m.reply(i18n.t(uid, f"سودو گرامی ظرفیت نصب تکمیل شده است و ظرفیت ربات • {limitcount} ! گروه میباشد", f"Dear sudo, the install capacity is full. The bot capacity is {limitcount} groups !"))

    req = await client.get_chat(chat_id)
    if req.invite_link is None:
        return await m.reply(i18n.t(uid, "**⌯** لطفا ربات را در گروه فول ادمین کرده و مجددا تلاش کنید **!**", "**⌯** Please make the bot full admin in the group and try again **!**"))
    database.execute("INSERT INTO gp(namegp, idgp, linkgp, status) VALUES(?,?,?,?)", (req.title, req.id, req.invite_link, 0))
    await m.reply(i18n.t(uid, "**⌯** گروه به لیست موزیک اضافه شد !", "**⌯** Group added to the music list !"))


@app.on_message(filters.group & (filters.regex(r"^(نصب موزیک)$") | filters.regex(r"^([Aa][Dd][Dd][Mm][Uu][Ss][Ii][Cc])$")))
async def addmusic(client, m: Message):
    await _add_music(client, m, m.chat.id)


@app.on_message(filters.group & (filters.regex(r"^(حذف موزیک)$") | filters.regex(r"^([Dd][Ee][Ll][Mm][Uu][Ss][Ii][Cc])$")))
async def delmusic(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    if database.insmusic() == []:
        return await m.reply(i18n.t(uid, "**⌯** هنوز گروهی برای دسترسی به پخش موزیک ثبت نکرده اید **!**", "**⌯** No group registered for music playback yet **!**"))
    database.execute("DELETE FROM musicadmin WHERE idgp=?", (m.chat.id,))
    database.execute("DELETE FROM gp WHERE idgp=? AND status=0", (m.chat.id,))
    database.execute("DELETE FROM charge WHERE idgp=?", (m.chat.id,))
    for target in (SUDO, OWNER):
        try:
            await app.send_message(target, f"دیتای موزیک گروه {m.chat.title} توسط {m.from_user.mention(m.from_user.first_name)} کاملا حذف شد !")
        except Exception:
            pass
    await m.reply(i18n.t(uid, "دیتای موزیک حذف شد !", "Music data deleted !"))


# ----------------------------------------------------------------------
# نصب ویدیو / addvideo
# ----------------------------------------------------------------------
async def _add_video(client, m: Message, chat_id):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    x = database.query("SELECT * FROM gp WHERE status=1")
    installed = [int(i[1]) for i in x]

    if not x:
        req = await client.get_chat(chat_id)
        if req.invite_link is None:
            return await m.reply(i18n.t(uid, "**⌯** لطفا ربات را در گروه فول ادمین کرده و مجددا تلاش کنید **!**", "**⌯** Please make the bot full admin in the group and try again **!**"))
        database.execute("INSERT INTO gp(namegp, idgp, linkgp, status) VALUES(?,?,?,?)", (req.title, req.id, req.invite_link, 1))
        await m.reply(i18n.t(uid, "**⌯** گروه به لیست ویدیو اضافه شد !", "**⌯** Group added to the video list !"))
        await _notify_install(client, m, "video")
        return

    if int(chat_id) in installed:
        return await m.reply(i18n.t(uid, "**⌯** این گروه در لیست ویدیو وجود دارد **!**", "**⌯** This group is already in the video list **!**"))

    limit_rows = database.query("SELECT status,count FROM limmit")
    if limit_rows:
        limitstatus, limitcount = limit_rows[0][0], limit_rows[0][1]
        if limitstatus == 1 and len(x) > limitcount:
            return await m.reply(i18n.t(uid, f"سودو گرامی ظرفیت نصب تکمیل شده است و ظرفیت ربات • {limitcount} ! گروه میباشد", f"Dear sudo, the install capacity is full. The bot capacity is {limitcount} groups !"))

    req = await client.get_chat(chat_id)
    if req.invite_link is None:
        return await m.reply(i18n.t(uid, "**⌯** لطفا ربات را در گروه فول ادمین کرده و مجددا تلاش کنید **!**", "**⌯** Please make the bot full admin in the group and try again **!**"))
    database.execute("INSERT INTO gp(namegp, idgp, linkgp, status) VALUES(?,?,?,?)", (req.title, req.id, req.invite_link, 1))
    await m.reply(i18n.t(uid, "**⌯** گروه به لیست ویدیو اضافه شد !", "**⌯** Group added to the video list !"))
    await _notify_install(client, m, "video")


async def _notify_install(client, m: Message, kind: str):
    try:
        req = await client.get_chat(m.chat.id)
        reqme = await client.get_me()
        uname = ("@" + reqme.username) if reqme.username else "ندارد !"
        title = "گروه ویدیو" if kind == "video" else "گروه موزیک"
        text = (
            f"**⇐یک {title} نصب شد !**\n\n"
            f"◂ تاریخ : {utils.jalali_now()}\n"
            f"┈┅┅━━| **مشخصات گروه** |━━┅┅┈\n"
            f"◂ نام گروه : `{m.chat.title}`\n"
            f"◂ شناسه گروه : `{m.chat.id}`\n"
            f"◂ لینک گروه : [برای ورود به گروه کلیک کنید.]({req.invite_link})\n"
            f"┈┅┅━━| **مشخصات همکار** |━━┅┅┈\n"
            f"◂ نام : `{m.from_user.first_name}`\n"
            f"◂ یوزرنیم : @{m.from_user.username}\n"
            f"◂ آیدی عددی : `{m.from_user.id}`\n"
            f"┈┅┅━━| **مشخصات ربات** |━━┅┅┈\n"
            f"◂ نام ربات : {reqme.first_name}\n"
            f"◂ شناسه : `{reqme.id}`\n"
            f"◂ نام کاربری : {uname}"
        )
        for target in (OWNER, SUDO):
            try:
                await client.send_message(target, text, disable_web_page_preview=True)
            except Exception:
                pass
    except Exception:
        pass


@app.on_message(filters.group & (filters.regex(r"^(نصب ویدیو)$") | filters.regex(r"^([Aa][Dd][Dd][Vv][Ii][Dd][Ee][Oo])$")))
async def addvideo(client, m: Message):
    await _add_video(client, m, m.chat.id)


@app.on_message(filters.group & (filters.regex(r"^(حذف ویدیو)$") | filters.regex(r"^([Dd][Ee][Ll][Vv][Ii][Dd][Ee][Oo])$")))
async def delvideo(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    if database.insvideo() == []:
        return await m.reply(i18n.t(uid, "**⌯** هنوز گروهی برای دسترسی به پخش ویدیو ثبت نکرده اید **!**", "**⌯** No group registered for video playback yet **!**"))
    database.execute("DELETE FROM videoadmins WHERE idgp=?", (m.chat.id,))
    database.execute("DELETE FROM gp WHERE idgp=? AND status=1", (m.chat.id,))
    database.execute("DELETE FROM charge2 WHERE idgp=?", (m.chat.id,))
    for target in (SUDO, OWNER):
        try:
            await app.send_message(target, f"دیتای ویدیو گروه {m.chat.title} توسط {m.from_user.mention(m.from_user.first_name)} کاملا حذف شد !")
        except Exception:
            pass
    await m.reply(i18n.t(uid, "دیتای ویدیو حذف شد !", "Video data deleted !"))


# ----------------------------------------------------------------------
# Music admins: ترفیع موزیک / عزل موزیک (reply & argument)
# ----------------------------------------------------------------------
def _music_installed(chat_id) -> bool:
    return database.query("SELECT idgp FROM gp WHERE status=0 AND idgp=?", (chat_id,)) != []


@app.on_message(filters.group & filters.reply & (filters.regex(r"^(ترفیع موزیک)$") | filters.regex(r"^([Pp][Rr][Oo][Mm][Oo][Tt][Ee][Mm][Uu][Ss][Ii][Cc])$")))
async def promotemusic_reply(client, m: Message):
    uid = m.from_user.id
    if not _music_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idadmin FROM musicadmin WHERE idgp=? AND idadmin=?", (m.chat.id, reply.id)) != []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر از قبل در لیست مدیران گروه وجود داشت **!**", "**⌯** The user was already in the music admins list **!**"))
    database.execute("INSERT INTO musicadmin(idgp, idadmin, nameadmin) VALUES(?,?,?)", (m.chat.id, reply.id, reply.first_name))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {reply.mention(reply.first_name)} به لیست مدیران موزیک اضافه شد **!**", f"**⌯** User {reply.mention(reply.first_name)} added to the music admins list **!**"))


@app.on_message(filters.group & filters.reply & (filters.regex(r"^(عزل موزیک)$") | filters.regex(r"^([Dd][Ee][Mm][Oo][Tt][Ee][Mm][Uu][Ss][Ii][Cc])$")))
async def demotemusic_reply(client, m: Message):
    uid = m.from_user.id
    if not _music_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idadmin FROM musicadmin WHERE idgp=? AND idadmin=?", (m.chat.id, reply.id)) == []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر در لیست مدیران موزیک وجود ندارد **!**", "**⌯** The user is not in the music admins list **!**"))
    database.execute("DELETE FROM musicadmin WHERE idgp=? AND idadmin=?", (m.chat.id, reply.id))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {reply.mention(reply.first_name)} از لیست مدیران موزیک حذف شد **!**", f"**⌯** User {reply.mention(reply.first_name)} removed from the music admins list **!**"))


@app.on_message(filters.group & (filters.regex(r"^([Pp][Rr][Oo][Mm][Oo][Tt][Ee][Mm][Uu][Ss][Ii][Cc])") | filters.regex(r"^(ترفیع موزیک)")))
async def promotemusic_arg(client, m: Message):
    uid = m.from_user.id
    if not _music_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    # the English name must match the regex above (`PromoteMusic`) - it was
    # misspelled `PromotMusic`, so the command word was never stripped and
    # `resolve_chat("PromoteMusic @user")` always failed with "User not found".
    text = utils.clean_command(m.text, "ترفیع موزیک", "PromoteMusic").lstrip("@")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "کاربر یافت نشد !", "User not found !"))
    if database.query("SELECT idadmin FROM musicadmin WHERE idgp=? AND idadmin=?", (m.chat.id, req.id)) != []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر از قبل در لیست مدیران گروه وجود داشت **!**", "**⌯** The user was already in the music admins list **!**"))
    database.execute("INSERT INTO musicadmin(idgp, idadmin, nameadmin) VALUES(?,?,?)", (m.chat.id, req.id, req.first_name))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {req.first_name} به لیست مدیران موزیک اضافه شد **!**", f"**⌯** User {req.first_name} added to the music admins list **!**"))


@app.on_message(filters.group & (filters.regex(r"^([Dd][Ee][Mm][Oo][Tt][Ee][Mm][Uu][Ss][Ii][Cc])") | filters.regex(r"^(عزل موزیک)")))
async def demotemusic_arg(client, m: Message):
    uid = m.from_user.id
    if not _music_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    text = utils.clean_command(m.text, "عزل موزیک", "DemoteMusic").lstrip("@")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "کاربر یافت نشد !", "User not found !"))
    if database.query("SELECT idadmin FROM musicadmin WHERE idgp=? AND idadmin=?", (m.chat.id, req.id)) == []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر در لیست مدیران موزیک وجود ندارد **!**", "**⌯** The user is not in the music admins list **!**"))
    database.execute("DELETE FROM musicadmin WHERE idgp=? AND idadmin=?", (m.chat.id, req.id))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {req.first_name} از لیست مدیران موزیک حذف شد **!**", f"**⌯** User {req.first_name} removed from the music admins list **!**"))


# ----------------------------------------------------------------------
# Video admins: ترفیع ویدیو / عزل ویدیو (reply & argument)
# ----------------------------------------------------------------------
def _video_installed(chat_id) -> bool:
    return database.query("SELECT idgp FROM gp WHERE status=1 AND idgp=?", (chat_id,)) != []


@app.on_message(filters.group & filters.reply & (filters.regex(r"^(ترفیع ویدیو)$") | filters.regex(r"^([Pp][Rr][Oo][Mm][Oo][Tt][Ee][Vv][Ii][Dd][Ee][Oo])$")))
async def promotevideo_reply(client, m: Message):
    uid = m.from_user.id
    if not _video_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idadmin FROM videoadmins WHERE idgp=? AND idadmin=?", (m.chat.id, reply.id)) != []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر از قبل در لیست مدیران گروه وجود داشت **!**", "**⌯** The user was already in the video admins list **!**"))
    database.execute("INSERT INTO videoadmins(idgp, idadmin, nameadmin) VALUES(?,?,?)", (m.chat.id, reply.id, reply.first_name))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {reply.mention(reply.first_name)} به لیست مدیران ویدیو اضافه شد **!**", f"**⌯** User {reply.mention(reply.first_name)} added to the video admins list **!**"))


@app.on_message(filters.group & filters.reply & (filters.regex(r"^(عزل ویدیو)$") | filters.regex(r"^([Dd][Ee][Mm][Oo][Tt][Ee][Vv][Ii][Dd][Ee][Oo])$")))
async def demotevideo_reply(client, m: Message):
    uid = m.from_user.id
    if not _video_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idadmin FROM videoadmins WHERE idgp=? AND idadmin=?", (m.chat.id, reply.id)) == []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر در لیست مدیران ویدیو وجود ندارد **!**", "**⌯** The user is not in the video admins list **!**"))
    database.execute("DELETE FROM videoadmins WHERE idgp=? AND idadmin=?", (m.chat.id, reply.id))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {reply.mention(reply.first_name)} از لیست مدیران ویدیو حذف شد **!**", f"**⌯** User {reply.mention(reply.first_name)} removed from the video admins list **!**"))


@app.on_message(filters.group & (filters.regex(r"^([Pp][Rr][Oo][Mm][Oo][Tt][Ee][Vv][Ii][Dd][Ee][Oo])") | filters.regex(r"^(ترفیع ویدیو)")))
async def promotevideo_arg(client, m: Message):
    uid = m.from_user.id
    if not _video_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    text = utils.clean_command(m.text, "ترفیع ویدیو", "PromoteVideo").lstrip("@")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "کاربر یافت نشد !", "User not found !"))
    if database.query("SELECT idadmin FROM videoadmins WHERE idgp=? AND idadmin=?", (m.chat.id, req.id)) != []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر از قبل در لیست مدیران گروه وجود داشت **!**", "**⌯** The user was already in the video admins list **!**"))
    database.execute("INSERT INTO videoadmins(idgp, idadmin, nameadmin) VALUES(?,?,?)", (m.chat.id, req.id, req.first_name))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {req.first_name} به لیست مدیران ویدیو اضافه شد **!**", f"**⌯** User {req.first_name} added to the video admins list **!**"))


@app.on_message(filters.group & (filters.regex(r"^([Dd][Ee][Mm][Oo][Tt][Ee][Vv][Ii][Dd][Ee][Oo])") | filters.regex(r"^(عزل ویدیو)")))
async def demotevideo_arg(client, m: Message):
    uid = m.from_user.id
    if not _video_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    text = utils.clean_command(m.text, "عزل ویدیو", "DemoteVideo").lstrip("@")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "کاربر یافت نشد !", "User not found !"))
    if database.query("SELECT idadmin FROM videoadmins WHERE idgp=? AND idadmin=?", (m.chat.id, req.id)) == []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر در لیست مدیران ویدیو وجود ندارد **!**", "**⌯** The user is not in the video admins list **!**"))
    database.execute("DELETE FROM videoadmins WHERE idgp=? AND idadmin=?", (m.chat.id, req.id))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {req.first_name} از لیست مدیران ویدیو حذف شد **!**", f"**⌯** User {req.first_name} removed from the video admins list **!**"))


# ----------------------------------------------------------------------
# لیست مدیران / پیکربندی / پاکسازی (music & video)
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(لیست مدیران موزیک)$") | filters.regex(r"^([Ll][Ii][Ss][Tt][Mm][Uu][Ss][Ii][Cc])$")))
async def list_music_admins(client, m: Message):
    uid = m.from_user.id
    if not _music_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    rows = database.query("SELECT * FROM musicadmin WHERE idgp=?", (m.chat.id,))
    if rows == []:
        return await m.reply(i18n.t(uid, "**⌯** لیست مدیران موزیک خالی میباشد **!**", "**⌯** The music admins list is empty **!**"))
    char = ""
    counter = 1
    for i in rows:
        char += f"❪{counter}❫ **-** [{i[2]}](tg://openmessage?user_id={i[1]}) **⊹** `{i[1]}`\n"
        counter += 1
    await m.reply(i18n.t(uid, "**⌯** لیست مدیران موزیک **:**\n┈┅───┤📋├───┅┈\n", "**⌯** Music admins list **:**\n┈┅───┤📋├───┅┈\n") + char)


@app.on_message(filters.group & (filters.regex(r"^(لیست مدیران ویدیو)$") | filters.regex(r"^([Ll][Ii][Ss][Tt][Vv][Ii][Dd][Ee][Oo])$")))
async def list_video_admins(client, m: Message):
    uid = m.from_user.id
    if not _video_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    rows = database.query("SELECT * FROM videoadmins WHERE idgp=?", (m.chat.id,))
    if rows == []:
        return await m.reply(i18n.t(uid, "**⌯** لیست مدیران ویدیو خالی میباشد **!**", "**⌯** The video admins list is empty **!**"))
    char = ""
    counter = 1
    for i in rows:
        char += f"❪{counter}❫ **-** [{i[2]}](tg://openmessage?user_id={i[1]}) **⊹** `{i[1]}`\n"
        counter += 1
    await m.reply(i18n.t(uid, "**⌯** لیست مدیران ویدیو **:**\n┈┅───┤📋├───┅┈\n", "**⌯** Video admins list **:**\n┈┅───┤📋├───┅┈\n") + char)


@app.on_message(filters.group & (filters.regex(r"^(پیکربندی موزیک)$") | filters.regex(r"^([Cc][Oo][Nn][Ff][Ii][Gg][Mm][Uu][Ss][Ii][Cc])$")))
async def config_music_admins(client, m: Message):
    uid = m.from_user.id
    if not _music_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    async for member in client.get_chat_members(m.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
        if member.user is None:
            continue
        if database.query("SELECT idadmin FROM musicadmin WHERE idgp=? AND idadmin=?", (m.chat.id, member.user.id)) == []:
            database.execute("INSERT INTO musicadmin(idgp, idadmin, nameadmin) VALUES(?,?,?)", (m.chat.id, member.user.id, member.user.first_name))
    await m.reply(i18n.t(uid, "**⌯** تمامی مدیران با موفقیت شناسایی و در ربات ترفیع یافتند **!**", "**⌯** All admins were detected and promoted **!**"))


@app.on_message(filters.group & (filters.regex(r"^(پیکربندی ویدیو)$") | filters.regex(r"^([Cc][Oo][Nn][Ff][Ii][Gg][Vv][Ii][Dd][Ee][Oo])$")))
async def config_video_admins(client, m: Message):
    uid = m.from_user.id
    if not _video_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    async for member in client.get_chat_members(m.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
        if member.user is None:
            continue
        if database.query("SELECT idadmin FROM videoadmins WHERE idgp=? AND idadmin=?", (m.chat.id, member.user.id)) == []:
            database.execute("INSERT INTO videoadmins(idgp, idadmin, nameadmin) VALUES(?,?,?)", (m.chat.id, member.user.id, member.user.first_name))
    await m.reply(i18n.t(uid, "**⌯** تمامی مدیران با موفقیت شناسایی و در ربات ترفیع یافتند **!**", "**⌯** All admins were detected and promoted **!**"))


@app.on_message(filters.group & (filters.regex(r"^(پاکسازی مدیران موزیک)$") | filters.regex(r"^([Dd][Ee][Ll][Cc][Oo][Nn][Ff][Ii][Gg][Mm][Uu][Ss][Ii][Cc])$")))
async def del_config_music(client, m: Message):
    uid = m.from_user.id
    if not _music_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    database.execute("DELETE FROM musicadmin WHERE idgp=?", (m.chat.id,))
    await m.reply(i18n.t(uid, "**⌯** تمامی مدیران با موفقیت از لیست مدیران موزیک حذف شدند **!**", "**⌯** All admins removed from the music admins list **!**"))


@app.on_message(filters.group & (filters.regex(r"^(پاکسازی مدیران ویدیو)$") | filters.regex(r"^([Dd][Ee][Ll][Cc][Oo][Nn][Ff][Ii][Gg][Vv][Ii][Dd][Ee][Oo])$")))
async def del_config_video(client, m: Message):
    uid = m.from_user.id
    if not _video_installed(m.chat.id) or not _creator(m.chat.id, uid):
        return
    database.execute("DELETE FROM videoadmins WHERE idgp=?", (m.chat.id,))
    await m.reply(i18n.t(uid, "**⌯** تمامی مدیران با موفقیت از لیست مدیران ویدیو حذف شدند **!**", "**⌯** All admins removed from the video admins list **!**"))


# ----------------------------------------------------------------------
# ترفیع مالک / عزل مالک / لیست مالکان (creators)
# ----------------------------------------------------------------------
@app.on_message(filters.group & filters.reply & (filters.regex(r"^(ترفیع مالک)$") | filters.regex(r"^([Ss][Ee][Tt][Cc][Rr][Ee][Aa][Tt][Oo][Rr])$")))
async def set_creator_reply(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner()):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idgp FROM gp WHERE idgp=?", (m.chat.id,)) == []:
        return await m.reply(i18n.t(uid, "• لطفا ابتدا گروه را نصب کنید !", "• Please install the group first !"))
    if database.query("SELECT creator FROM creators WHERE creator=?", (reply.id,)) != []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر از قبل در لیست مالک ها بود **!**", "**⌯** The user was already in the owners list **!**"))
    database.execute("INSERT INTO creators(idgp, creator) VALUES(?,?)", (m.chat.id, reply.id))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {reply.mention(reply.first_name)} با موفقیت به لیست مالکین گروه اضافه شد **!**", f"**⌯** User {reply.mention(reply.first_name)} added to the group owners list **!**"))


@app.on_message(filters.group & filters.reply & (filters.regex(r"^(عزل مالک)$") | filters.regex(r"^([Dd][Ee][Ll][Cc][Rr][Ee][Aa][Tt][Oo][Rr])$")))
async def del_creator_reply(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner()):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idgp FROM gp WHERE idgp=?", (m.chat.id,)) == []:
        return await m.reply(i18n.t(uid, "• لطفا ابتدا گروه را نصب کنید !", "• Please install the group first !"))
    if database.query("SELECT creator FROM creators WHERE creator=?", (reply.id,)) == []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر در لیست مالکان گروه وجود ندارد **!**", "**⌯** The user is not in the group owners list **!**"))
    database.execute("DELETE FROM creators WHERE creator=?", (reply.id,))
    await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر از لیست مالکان گروه حذف شد **!**", "**⌯** The user was removed from the group owners list **!**"))


@app.on_message(filters.group & (filters.regex(r"^(ترفیع مالک)") | filters.regex(r"^([Ss][Ee][Tt][Cc][Rr][Ee][Aa][Tt][Oo][Rr])")))
async def set_creator_arg(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner()):
        return
    text = utils.clean_command(m.text, "ترفیع مالک", "SetCreator").lstrip("@")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "• کاربر یافت نشد !", "• User not found !"))
    if database.query("SELECT idgp FROM gp WHERE idgp=?", (m.chat.id,)) == []:
        return await m.reply(i18n.t(uid, "• لطفا ابتدا گروه را نصب کنید !", "• Please install the group first !"))
    if database.query("SELECT creator FROM creators WHERE creator=?", (req.id,)) != []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر از قبل در لیست مالک ها بود **!**", "**⌯** The user was already in the owners list **!**"))
    database.execute("INSERT INTO creators(idgp, creator) VALUES(?,?)", (m.chat.id, req.id))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {req.first_name} با موفقیت به لیست مالکین گروه اضافه شد **!**", f"**⌯** User {req.first_name} added to the group owners list **!**"))


@app.on_message(filters.group & (filters.regex(r"^(عزل مالک)") | filters.regex(r"^([Dd][Ee][Ll][Cc][Rr][Ee][Aa][Tt][Oo][Rr])")))
async def del_creator_arg(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner()):
        return
    text = utils.clean_command(m.text, "عزل مالک", "DelCreator").lstrip("@")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "• کاربر یافت نشد !", "• User not found !"))
    if database.query("SELECT idgp FROM gp WHERE idgp=?", (m.chat.id,)) == []:
        return await m.reply(i18n.t(uid, "• لطفا ابتدا گروه را نصب کنید !", "• Please install the group first !"))
    if database.query("SELECT creator FROM creators WHERE creator=?", (req.id,)) == []:
        return await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر در لیست مالکان گروه وجود ندارد **!**", "**⌯** The user is not in the group owners list **!**"))
    database.execute("DELETE FROM creators WHERE creator=?", (req.id,))
    await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر از لیست مالکان گروه حذف شد **!**", "**⌯** The user was removed from the group owners list **!**"))


@app.on_message(filters.group & (filters.regex(r"^(لیست مالکان)$") | filters.regex(r"^([Cc][Rr][Ee][Aa][Tt][Oo][Rr][Ss][Ll][Ii][Ss][Tt])$")))
async def creators_list(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner(), *database.creators(m.chat.id)):
        return
    rows = database.query("SELECT creator FROM creators WHERE idgp=?", (m.chat.id,))
    if rows == []:
        return await m.reply(i18n.t(uid, "• لیست مالکان خالی میباشد !", "• The owners list is empty !"))
    text = ""
    counter = 1
    for r in rows:
        try:
            chat = await client.get_chat(r[0])
            name = chat.first_name or "?"
        except Exception:
            name = "?"
        text += f"❪{counter}❫ **-** [{name}](tg://openmessage?user_id={r[0]}) **⊹** `{r[0]}`\n"
        counter += 1
    await m.reply(i18n.t(uid, "**⌯** لیست مالکان **:**\n┈┅───┤📋├───┅┈\n", "**⌯** Owners list **:**\n┈┅───┤📋├───┅┈\n") + text)


# ----------------------------------------------------------------------
# تنظیم سودو / حذف سودو (group) + (private via argument)
# ----------------------------------------------------------------------
@app.on_message(filters.group & filters.user([OWNER, SUDO]) & (filters.regex(r"^(تنظیم سودو)") | filters.regex(r"^([Ss][Ee][Tt][Ss][Uu][Dd][Oo])")))
async def set_sudo_group(client, m: Message):
    uid = m.from_user.id
    text = utils.clean_command(m.text, "تنظیم سودو", "SetSudo")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "کاربر یافت نشد !", "User not found !"))
    if database.query("SELECT idsudo FROM sudo WHERE idsudo=?", (req.id,)) != []:
        return await m.reply(i18n.t(uid, f"• کاربر {req.first_name} از قبل در لیست سودو ها بود !", f"• User {req.first_name} is already a sudo !"))
    database.execute("INSERT INTO sudo(idsudo, namesudo) VALUES(?,?)", (req.id, req.first_name))
    await m.reply(i18n.t(uid, f"• کاربر {req.first_name} با موفقیت به لیست سودو ها اضافه شد !", f"• User {req.first_name} added to the sudo list !"))


@app.on_message(filters.group & filters.user([OWNER, SUDO]) & (filters.regex(r"^(حذف سودو)") | filters.regex(r"^([Dd][Ee][Ll][Ss][Uu][Dd][Oo])")))
async def del_sudo_group(client, m: Message):
    uid = m.from_user.id
    text = utils.clean_command(m.text, "حذف سودو", "DelSudo")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "• کاربر یافت نشد !", "• User not found !"))
    if database.query("SELECT idsudo FROM sudo WHERE idsudo=?", (req.id,)) != []:
        database.execute("DELETE FROM sudo WHERE idsudo=?", (req.id,))
        return await m.reply(i18n.t(uid, f"**⌯** کاربر {req.first_name} با موفقیت از لیست سودو ها حذف شد **!**", f"**⌯** User {req.first_name} removed from the sudo list **!**"))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {req.first_name} در لیست سودو ها یافت نشد **!**", f"**⌯** User {req.first_name} not found in the sudo list **!**"))


@app.on_message(filters.private & filters.user(OWNER) & (filters.regex(r"^(تنظیم سودو)") | filters.regex(r"^([Ss][Ee][Tt][Ss][Uu][Dd][Oo])")))
async def set_sudo_private(client, m: Message):
    uid = m.from_user.id
    text = utils.clean_command(m.text, "تنظیم سودو", "SetSudo")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "کاربر یافت نشد !", "User not found !"))
    if database.query("SELECT idsudo FROM sudo WHERE idsudo=?", (req.id,)) != []:
        return await m.reply(i18n.t(uid, f"• کاربر {req.first_name} از قبل در لیست سودو ها بود !", f"• User {req.first_name} is already a sudo !"))
    database.execute("INSERT INTO sudo(idsudo, namesudo) VALUES(?,?)", (req.id, req.first_name))
    await m.reply(i18n.t(uid, f"• کاربر {req.first_name} با موفقیت به لیست سودو ها اضافه شد !", f"• User {req.first_name} added to the sudo list !"))


@app.on_message(filters.private & filters.user(OWNER) & (filters.regex(r"^(حذف سودو)") | filters.regex(r"^([Dd][Ee][Ll][Ss][Uu][Dd][Oo])")))
async def del_sudo_private(client, m: Message):
    uid = m.from_user.id
    text = utils.clean_command(m.text, "حذف سودو", "DelSudo")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "• کاربر یافت نشد !", "• User not found !"))
    if database.query("SELECT idsudo FROM sudo WHERE idsudo=?", (req.id,)) != []:
        database.execute("DELETE FROM sudo WHERE idsudo=?", (req.id,))
        return await m.reply(i18n.t(uid, f"**⌯** کاربر {req.first_name} با موفقیت از لیست سودو ها حذف شد **!**", f"**⌯** User {req.first_name} removed from the sudo list **!**"))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {req.first_name} در لیست سودو ها یافت نشد **!**", f"**⌯** User {req.first_name} not found in the sudo list **!**"))


# ----------------------------------------------------------------------
# تنظیم ادمین / حذف ادمین (group, reply) -> owner table
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(تنظیم ادمین)$") | filters.regex(r"^([Ss][Ee][Tt][Aa][Dd][Mm][Ii][Nn])$")))
async def set_admin_group(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos()):
        return
    if not m.reply_to_message or m.reply_to_message.from_user is None:
        return
    reply = m.reply_to_message.from_user
    if database.query("SELECT idowner FROM owner WHERE idowner=?", (reply.id,)) != []:
        return await m.reply(i18n.t(uid, f"**⌯** کاربر {reply.mention(reply.first_name)} از قبل در لیست ادمین های ربات وجود داشت **!**", f"**⌯** User {reply.mention(reply.first_name)} is already in the bot admin list **!**"))
    database.execute("INSERT INTO owner(idowner, nameowner) VALUES(?,?)", (reply.id, reply.first_name))
    await m.reply(i18n.t(uid, f"**⌯** کاربر {reply.mention(reply.first_name)} با موفقیت به لیست ادمین های ربات اضافه شد **!**", f"**⌯** User {reply.mention(reply.first_name)} added to the bot admin list **!**"))


@app.on_message(filters.group & (filters.regex(r"^(حذف ادمین)$") | filters.regex(r"^([Rr][Ee][Mm][Aa][Dd][Mm][Ii][Nn])$")))
async def del_admin_group(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos()):
        return
    if not m.reply_to_message or m.reply_to_message.from_user is None:
        return
    reply = m.reply_to_message.from_user
    if database.query("SELECT idowner FROM owner WHERE idowner=?", (reply.id,)) != []:
        database.execute("DELETE FROM owner WHERE idowner=?", (reply.id,))
        return await m.reply(i18n.t(uid, f"**⌯** کاربر {reply.mention(reply.first_name)} از لیست ادمین های ربات حذف شد **!**", f"**⌯** User {reply.mention(reply.first_name)} removed from the bot admin list **!**"))
    await m.reply(i18n.t(uid, "**⌯** کاربر مورد نظر در لیست ادمین های ربات یافت نشد **!**", "**⌯** The user was not found in the bot admin list **!**"))


# ----------------------------------------------------------------------
# Global music/video admins: همگانی موزیک / همگانی ویدیو (alll table)
# ----------------------------------------------------------------------
@app.on_message(filters.group & filters.reply & (filters.regex(r"^(همگانی موزیک)$") | filters.regex(r"^([Aa][Ll][Ll][Mm][Uu][Ss][Ii][Cc])$")))
async def allmusic_add(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idsadmin FROM alll WHERE idsadmin=? AND status=0", (reply.id,)) != []:
        return await m.reply(i18n.t(uid, "• این کاربر از قبل در لیست مدیران همگانی موزیک است !", "• This user is already a global music admin !"))
    database.execute("INSERT INTO alll(idsadmin, namesadmin, status) VALUES(?,?,?)", (reply.id, reply.first_name, 0))
    await m.reply(i18n.t(uid, f"• کاربر {reply.mention(reply.first_name)} به لیست مدیران همگانی موزیک اضافه شد !", f"• User {reply.mention(reply.first_name)} added to the global music admins !"))


@app.on_message(filters.group & (filters.regex(r"^(حذف همگانی موزیک)$") | filters.regex(r"^([Dd][Ee][Ll][Aa][Ll][Ll][Mm][Uu][Ss][Ii][Cc])$")))
async def allmusic_del(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    text = utils.clean_command(m.text, "حذف همگانی موزیک", "DelAllMusic")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "• کاربر یافت نشد !", "• User not found !"))
    database.execute("DELETE FROM alll WHERE idsadmin=? AND status=0", (req.id,))
    await m.reply(i18n.t(uid, f"• کاربر {req.first_name} از لیست مدیران همگانی موزیک حذف شد !", f"• User {req.first_name} removed from the global music admins !"))


@app.on_message(filters.group & filters.reply & (filters.regex(r"^(همگانی ویدیو)$") | filters.regex(r"^([Aa][Ll][Ll][Vv][Ii][Dd][Ee][Oo])$")))
async def allvideo_add(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idsadmin FROM alll WHERE idsadmin=? AND status=1", (reply.id,)) != []:
        return await m.reply(i18n.t(uid, "• این کاربر از قبل در لیست مدیران همگانی ویدیو است !", "• This user is already a global video admin !"))
    database.execute("INSERT INTO alll(idsadmin, namesadmin, status) VALUES(?,?,?)", (reply.id, reply.first_name, 1))
    await m.reply(i18n.t(uid, f"• کاربر {reply.mention(reply.first_name)} به لیست مدیران همگانی ویدیو اضافه شد !", f"• User {reply.mention(reply.first_name)} added to the global video admins !"))


@app.on_message(filters.group & (filters.regex(r"^(حذف همگانی ویدیو)$") | filters.regex(r"^([Dd][Ee][Ll][Aa][Ll][Ll][Vv][Ii][Dd][Ee][Oo])$")))
async def allvideo_del(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    text = utils.clean_command(m.text, "حذف همگانی ویدیو", "DelAllVideo")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "• کاربر یافت نشد !", "• User not found !"))
    database.execute("DELETE FROM alll WHERE idsadmin=? AND status=1", (req.id,))
    await m.reply(i18n.t(uid, f"• کاربر {req.first_name} از لیست مدیران همگانی ویدیو حذف شد !", f"• User {req.first_name} removed from the global video admins !"))


# ----------------------------------------------------------------------
# Charge commands: تنظیم شارژ / آپدیت شارژ (private & group)
# ----------------------------------------------------------------------
@app.on_message(filters.private & (filters.regex(r"^(تنظیم شارژ ویدیو)") | filters.regex(r"^(آپدیت شارژ ویدیو)") | filters.regex(r"^(اپدیت شارژ ویدیو)")))
async def charge_video_private(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    text = utils.msg_text(m)
    for p in ("تنظیم شارژ ویدیو", "آپدیت شارژ ویدیو", "اپدیت شارژ ویدیو"):
        text = text.replace(p, "")
    parts = text.split()
    if len(parts) < 2:
        return await m.reply(i18n.t(uid, "• فرمت : تنظیم شارژ ویدیو [شناسه گروه] [تعداد روز]", "• Format : set charge video [group id] [days]"))
    try:
        gid, days = int(parts[0]), int(parts[1])
    except ValueError:
        return await m.reply(i18n.t(uid, "• شناسه و روز باید عدد باشند !", "• Id and days must be numbers !"))
    if database.query("SELECT idgp FROM charge2 WHERE idgp=?", (gid,)) != []:
        database.execute("UPDATE charge2 SET day=?, end=?, status=0 WHERE idgp=?", (days, time.time() + float(days * 24 * 60 * 60), gid))
        await m.reply(i18n.t(uid, "**⌯** شارژ ویدیو آپدیت شد **!**", "**⌯** Video charge updated **!**"))
    else:
        await m.reply(i18n.t(uid, "**⌯** گروه مورد نظر یافت نشد **!**", "**⌯** Group not found **!**"))
    await m.stop_propagation()


@app.on_message(filters.group & (filters.regex(r"^(تنظیم شارژ ویدیو)") | filters.regex(r"^(آپدیت شارژ ویدیو)") | filters.regex(r"^(اپدیت شارژ ویدیو)")))
async def charge_video_group(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    text = utils.msg_text(m)
    for p in ("تنظیم شارژ ویدیو", "آپدیت شارژ ویدیو", "اپدیت شارژ ویدیو"):
        text = text.replace(p, "")
    text = text.strip()
    if not text.isdigit():
        return await m.reply(i18n.t(uid, "**⌯** شارژ گروه باید به صورت عدد باشد **!**", "**⌯** The charge must be a number **!**"))
    days = int(text)
    if database.query("SELECT idgp FROM charge2 WHERE idgp=?", (m.chat.id,)) != []:
        database.execute("UPDATE charge2 SET day=?, end=?, status=0 WHERE idgp=?", (days, time.time() + float(days * 24 * 60 * 60), m.chat.id))
        await m.reply(i18n.t(uid, "**⌯** شارژ گروه آپدیت شد **!**", "**⌯** Group charge updated **!**"))
    else:
        await m.reply(i18n.t(uid, "**⌯** این گروه فاقد اعتبار است لطفا ابتدا آن را شارژ کنید **!**", "**⌯** This group has no charge yet - please charge it first **!**"))
    await m.stop_propagation()


@app.on_message(filters.private & (filters.regex(r"^(تنظیم شارژ)(?! ویدیو)") | filters.regex(r"^(آپدیت شارژ)(?! ویدیو)") | filters.regex(r"^(اپدیت شارژ)(?! ویدیو)")))
async def charge_music_private(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    text = utils.msg_text(m)
    for p in ("تنظیم شارژ", "آپدیت شارژ", "اپدیت شارژ"):
        text = text.replace(p, "")
    parts = text.split()
    if len(parts) < 2:
        return await m.reply(i18n.t(uid, "• فرمت : تنظیم شارژ [شناسه گروه] [تعداد روز]", "• Format : set charge [group id] [days]"))
    try:
        gid, days = int(parts[0]), int(parts[1])
    except ValueError:
        return await m.reply(i18n.t(uid, "• شناسه و روز باید عدد باشند !", "• Id and days must be numbers !"))
    if database.query("SELECT idgp FROM charge WHERE idgp=?", (gid,)) != []:
        database.execute("UPDATE charge SET day=?, end=?, status=0 WHERE idgp=?", (days, time.time() + float(days * 24 * 60 * 60), gid))
        await m.reply(i18n.t(uid, "**⌯** شارژ موزیک آپدیت شد **!**", "**⌯** Music charge updated **!**"))
    else:
        await m.reply(i18n.t(uid, "**⌯** گروه مورد نظر یافت نشد **!**", "**⌯** Group not found **!**"))


@app.on_message(filters.group & (filters.regex(r"^(تنظیم شارژ)(?! ویدیو)") | filters.regex(r"^(آپدیت شارژ)(?! ویدیو)") | filters.regex(r"^(اپدیت شارژ)(?! ویدیو)")))
async def charge_music_group(client, m: Message):
    uid = m.from_user.id
    if not _sudo(uid):
        return
    text = utils.msg_text(m)
    for p in ("تنظیم شارژ", "آپدیت شارژ", "اپدیت شارژ"):
        text = text.replace(p, "")
    text = text.strip()
    if not text.isdigit():
        return await m.reply(i18n.t(uid, "**⌯** شارژ گروه باید به صورت عدد باشد **!**", "**⌯** The charge must be a number **!**"))
    days = int(text)
    if database.query("SELECT idgp FROM charge WHERE idgp=?", (m.chat.id,)) != []:
        database.execute("UPDATE charge SET day=?, end=?, status=0 WHERE idgp=?", (days, time.time() + float(days * 24 * 60 * 60), m.chat.id))
        await m.reply(i18n.t(uid, "**⌯** شارژ گروه آپدیت شد **!**", "**⌯** Group charge updated **!**"))
    else:
        await m.reply(i18n.t(uid, "**⌯** این گروه فاقد اعتبار است لطفا ابتدا آن را شارژ کنید **!**", "**⌯** This group has no charge yet - please charge it first **!**"))


# ----------------------------------------------------------------------
# اعتبار / credit
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^اعتبار$") | filters.regex(r"^[Cc][Rr][Ee][Dd][Ii][Tt]$")))
async def group_credit(client, m: Message):
    uid = m.from_user.id
    admins = []
    async for member in client.get_chat_members(m.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
        # anonymous/channel admins can arrive with user=None (see the same
        # guard in addmusicadmins / addvideoadmins)
        if member.user is None:
            continue
        admins.append(member.user.id)
    admins.extend(database.idsudos())
    admins.extend([OWNER, SUDO])
    if uid not in admins:
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return

    c_id = str(m.chat.id)
    etebar_music, status_music = 0, 0
    etebar_video, status_video = 0, 0

    rows = database.query("SELECT * FROM charge WHERE idgp=?", (c_id,))
    if rows:
        eteb = rows[0]
        if eteb[5] == 0:
            etebar_music = int(int(eteb[4] - time.time()) / 60 / 60 / 24)
            status_music = 0
        elif eteb[5] == 1:
            etebar_music = int(int(eteb[4] - time.time()) / 60 / 60)
            status_music = 1
    rows2 = database.query("SELECT * FROM charge2 WHERE idgp=?", (c_id,))
    if rows2:
        eteb = rows2[0]
        if eteb[5] == 0:
            etebar_video = int(int(eteb[4] - time.time()) / 60 / 60 / 24)
            status_video = 0
        elif eteb[5] == 1:
            etebar_video = int(int(eteb[4] - time.time()) / 60 / 60)
            status_video = 1

    unit_m = "ساعت" if status_music == 1 else "روز"
    unit_v = "ساعت" if status_video == 1 else "روز"
    await m.reply(
        i18n.t(
            uid,
            f"**⌯** گروه شما به مدت {etebar_music} {unit_m} اعتبار موزیک و به مدت {etebar_video} {unit_v} اعتبار ویدیو دارد **!**",
            f"**⌯** Your group has {etebar_music} {unit_m} of music credit and {etebar_video} {unit_v} of video credit **!**",
        )
    )


# ----------------------------------------------------------------------
# آیدی / id
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^[Ii][Dd]$") | filters.regex(r"^آیدی$") | filters.regex(r"^ایدی$")))
async def id_command(client, m: Message):
    uid = m.from_user.id
    sudos = [*database.idsudos(), SUDO, OWNER]
    if uid not in sudos:
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    target = m.reply_to_message.from_user if m.reply_to_message and m.reply_to_message.from_user else m.from_user
    first_name = target.first_name
    user_id = target.id
    username = target.username
    role = (
        "برنامه نویس" if user_id == OWNER
        else "مالک ربات" if user_id == SUDO
        else "ادمین ربات" if user_id in sudos
        else "--"
    )
    fa = (
        f"┈┅┅━┃**اطلاعات کاربر**┃━┅┅┈\n"
        f"⋆ نام : {first_name}\n"
        f"⋆ شناسه : `{user_id}`\n"
        f"⋆ نام کاربری : @{username}\n"
        f"⋆ مقام : {role}\n"
        f"┈┅┅━┃**شناسه گروه**┃━┅┅┈\n"
        f"⋆ شناسه : `{m.chat.id}`"
    )
    en = (
        f"┈┅┅━┃**User Info**┃━┅┅┈\n"
        f"⋆ Name : {first_name}\n"
        f"⋆ Id : `{user_id}`\n"
        f"⋆ Username : @{username}\n"
        f"⋆ Role : {role}\n"
        f"┈┅┅━┃**Group Id**┃━┅┅┈\n"
        f"⋆ Id : `{m.chat.id}`"
    )
    try:
        async for photo in client.get_chat_photos(user_id, limit=1):
            await client.send_photo(m.chat.id, photo.file_id, caption=i18n.t(uid, fa, en), reply_to_message_id=m.id)
            return
    except Exception:
        pass
    await m.reply(i18n.t(uid, fa, en))


# ----------------------------------------------------------------------
# خروج (leave) - private & group
# ----------------------------------------------------------------------
@app.on_message(filters.private & (filters.regex(r"^خروج")))
async def leave_private(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos()):
        return
    text = utils.msg_text(m).replace("خروج ", "").replace("-100", "").strip()
    try:
        gid = int("-100" + text)
    except ValueError:
        return await m.reply(i18n.t(uid, "**⌯** لطفا آیدی عددی گروه را درست وارد کنید **!**", "**⌯** Please enter a valid group id **!**"))
    try:
        await app.send_message(gid, i18n.t(uid, "**⌯** ربات از این گروه خارج میشود **!**", "**⌯** The bot is leaving this group **!**"))
        await app.leave_chat(gid)
        from clients import ubot, helper_ready
        if helper_ready():
            try:
                await ubot.leave_chat(gid)
            except Exception:
                pass
        await m.reply(i18n.t(uid, "**⌯** ربات با موفقیت از گروه مورد نظر خارج شد **!**", "**⌯** The bot left the group successfully **!**"))
    except Exception:
        await m.reply(i18n.t(uid, "**⌯** گروه یافت نشد **!**", "**⌯** Group not found **!**"))


@app.on_message(filters.group & filters.regex(r"^خروج$"))
async def leave_group(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos()):
        return
    await m.reply(i18n.t(uid, "**⌯** ربات از این گروه خارج میشود **!**", "**⌯** The bot is leaving this group **!**"))
    await app.leave_chat(m.chat.id)
    from clients import helper_ready
    if helper_ready():
        try:
            from clients import ubot
            await ubot.leave_chat(m.chat.id)
        except Exception:
            pass


# ----------------------------------------------------------------------
# شروع ویس کال / start voice call
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(شروع ویس کال)$") | filters.regex(r"^([Ss][Tt][Aa][Rr][Tt][Vv][Oo][Ii][Cc][Ee][Cc][Aa][Ll][Ll])$")))
async def start_voice_call(client, m: Message):
    uid = m.from_user.id
    access = [*database.idsudos(), *database.idowner(), *database.idmusic(m.chat.id), *database.idvideo(m.chat.id),
              *database.creators(m.chat.id), SUDO, OWNER, *database.allmusic(), *database.allvideo()]
    if uid not in access:
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    installed = [*database.insmusic(), *database.insvideo()]
    if m.chat.id not in installed:
        return
    from clients import ubot, helper_ready
    if not helper_ready():
        return await m.reply(i18n.t(uid, "• حساب هلپر وارد نشده است ! لطفا ابتدا /login را انجام دهید.", "• The helper account is not logged in ! Please run /login first."))
    try:
        from pyrogram.raw.functions.phone import CreateGroupCall
        peer = await ubot.resolve_peer(m.chat.id)
        await ubot.invoke(CreateGroupCall(peer=peer, random_id=random_id()))
        await m.reply(i18n.t(uid, "• تماس گروهی با موفقیت راه اندازی شد !", "• Group call started successfully !"))
    except Exception:
        await m.reply(i18n.t(uid, "• راه اندازی تماس گروهی به مشکل خورده است !", "• Failed to start the group call !"))


def random_id():
    import random
    return random.randint(1, 2**31 - 1)


# ----------------------------------------------------------------------
# بن همگانی / ازاد همگانی (banlist)
# ----------------------------------------------------------------------
@app.on_message(filters.group & filters.user([OWNER, SUDO]) & (filters.regex(r"^(بن همگانی)") | filters.regex(r"^([Bb][Aa][Nn][Aa][Ll][Ll])")))
async def ban_all(client, m: Message):
    uid = m.from_user.id
    text = utils.clean_command(m.text, "بن همگانی", "BanAll")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "• کاربر یافت نشد !", "• User not found !"))
    if database.query("SELECT ban FROM banlist WHERE ban=?", (req.id,)) != []:
        return await m.reply(i18n.t(uid, "• این کاربر از قبل در لیست بن همگانی است !", "• This user is already on the global ban list !"))
    database.execute("INSERT INTO banlist(idgp, ban) VALUES(?,?)", (m.chat.id, req.id))
    await m.reply(i18n.t(uid, f"• کاربر {req.first_name} به لیست بن همگانی اضافه شد !", f"• User {req.first_name} added to the global ban list !"))


@app.on_message(filters.group & filters.user([OWNER, SUDO]) & (filters.regex(r"^(ازاد همگانی)") | filters.regex(r"^([Uu][Nn][Bb][Aa][Nn][Aa][Ll][Ll])")))
async def unban_all(client, m: Message):
    uid = m.from_user.id
    text = utils.clean_command(m.text, "ازاد همگانی", "UnbanAll")
    req = await utils.resolve_chat(text)
    if req is None:
        return await m.reply(i18n.t(uid, "• کاربر یافت نشد !", "• User not found !"))
    database.execute("DELETE FROM banlist WHERE ban=?", (req.id,))
    await m.reply(i18n.t(uid, f"• کاربر {req.first_name} از لیست بن همگانی حذف شد !", f"• User {req.first_name} removed from the global ban list !"))


# ----------------------------------------------------------------------
# Force-join exemptions: معاف اجبار / تنظیم اجبار / لیست معافیت
# ----------------------------------------------------------------------
@app.on_message(filters.group & filters.reply & filters.regex(r"^(معاف اجبار)$"))
async def exempt_force_join(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner(), *database.creators(m.chat.id)):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idadmin FROM ejbar WHERE idgp=? AND idadmin=?", (m.chat.id, reply.id)) != []:
        return await m.reply(i18n.t(uid, "• کاربر مورد نظر از قبل در لیست معافیت وجود داشت !", "• The user is already on the exemption list !"))
    database.execute("INSERT INTO ejbar(idgp, idadmin) VALUES(?,?)", (m.chat.id, reply.id))
    await m.reply(i18n.t(uid, f"• کاربر {reply.mention(reply.first_name)} به لیست معافیت اضافه شد !", f"• User {reply.mention(reply.first_name)} added to the exemption list !"))


@app.on_message(filters.group & filters.reply & filters.regex(r"^(تنظیم اجبار)$"))
async def unexempt_force_join(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner(), *database.creators(m.chat.id)):
        return
    reply = m.reply_to_message.from_user
    if reply is None:
        return
    if database.query("SELECT idadmin FROM ejbar WHERE idgp=? AND idadmin=?", (m.chat.id, reply.id)) == []:
        return await m.reply(i18n.t(uid, "• کاربر مورد نظر در لیست معافیت وجود نداشت !", "• The user is not on the exemption list !"))
    database.execute("DELETE FROM ejbar WHERE idgp=? AND idadmin=?", (m.chat.id, reply.id))
    await m.reply(i18n.t(uid, f"کاربر {reply.mention(reply.first_name)} از لیست معافیت حذف شد !", f"User {reply.mention(reply.first_name)} removed from the exemption list !"))


@app.on_message(filters.group & filters.regex(r"^(لیست معافیت)$"))
async def exemption_list(client, m: Message):
    uid = m.from_user.id
    if uid not in (OWNER, SUDO, *database.idsudos(), *database.idowner(), *database.creators(m.chat.id)):
        return
    rows = database.query("SELECT idadmin FROM ejbar WHERE idgp=?", (m.chat.id,))
    if rows == []:
        return await m.reply(i18n.t(uid, "• لیست معافیت خالی میباشد !", "• The exemption list is empty !"))
    charlist = ""
    for r in rows:
        req = await utils.resolve_chat(r[0])
        name = req.first_name if req else str(r[0])
        charlist += f"{name} -> {r[0]}\n"
    await m.reply(i18n.t(uid, "**⌯** لیست معافیت **:**\n┈┅───┤📋├───┅┈\n", "**⌯** Exemption list **:**\n┈┅───┤📋├───┅┈\n") + charlist)


# ----------------------------------------------------------------------
# پاکسازی downloads (owner)
# ----------------------------------------------------------------------
@app.on_message(filters.user(OWNER) & filters.regex(r"^پاکسازی$"))
async def clear_downloads(client, m: Message):
    uid = m.from_user.id
    try:
        # `downloads/<chat_id>/<title>.mp3` files are referenced by the
        # `playlist` table (add_to_playlist). Deleting them used to leave the
        # DB rows behind, so پخش لیست silently skipped every single track.
        # Only remove files that nothing references any more.
        keep = {os.path.abspath(r[0]) for r in database.query("SELECT path FROM playlist") if r[0]}

        removed = kept = 0
        for f in os.listdir(cfg.DOWNLOAD_DIR):
            p = os.path.join(cfg.DOWNLOAD_DIR, f)
            if os.path.isfile(p):
                if os.path.abspath(p) in keep:
                    kept += 1
                else:
                    os.remove(p)
                    removed += 1
            else:
                # walk the sub-folder and keep referenced files in place
                for root, _dirs, files in os.walk(p, topdown=False):
                    for name in files:
                        fp = os.path.join(root, name)
                        if os.path.abspath(fp) in keep:
                            kept += 1
                            continue
                        try:
                            os.remove(fp)
                            removed += 1
                        except OSError:
                            pass
                    # drop the directory itself once it is empty
                    try:
                        os.rmdir(root)
                    except OSError:
                        pass

        if kept:
            msg_fa = (
                f"**⌯** پوشه ی \"downloads\" پاکسازی شد **!**\n"
                f"**⊹** حذف شد : {removed} فایل\n"
                f"**⊹** نگه داشته شد : {kept} فایل (عضو لیست پخش)\n"
                f"**⊹** برای حذف آن ها ابتدا `پاکسازی لیست پخش` را در گروه مربوطه بزنید."
            )
            msg_en = (
                f"**⌯** The \"downloads\" folder was cleaned **!**\n"
                f"**⊹** Removed : {removed} file(s)\n"
                f"**⊹** Kept : {kept} file(s) (part of a playlist)\n"
                f"**⊹** To remove those, run `cleanplaylist` in the group first."
            )
        else:
            msg_fa = f"**⌯** پوشه ی \"downloads\" با موفقیت پاکسازی شد **!** ({removed} فایل)"
            msg_en = f"**⌯** The \"downloads\" folder was cleaned **!** ({removed} file(s))"
        await m.reply(i18n.t(uid, msg_fa, msg_en))
    except Exception:
        await m.reply(i18n.t(uid, "• پاکسازی با مشکل مواجه شد !", "• Cleaning failed !"))

