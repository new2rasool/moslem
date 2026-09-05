"""
Inline callbacks: install / charge / configure / add-helper / delete
panels. Button layout and behavior identical to the original bot.
"""
import time

from pyrogram import enums
from pyrogram.types import CallbackQuery, ChatPrivileges, InlineKeyboardButton, InlineKeyboardMarkup

import config
import database
import i18n
import utils
from clients import app, call_py, ubot, helper_session_exists

cfg = config.get_config()
OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID


# ----------------------------------------------------------------------
def panel_markup(uid):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(uid, "• نصب ویدیو", "• Install Video"), callback_data="installvideo"),
             InlineKeyboardButton(i18n.t(uid, "• نصب موزیک", "• Install Music"), callback_data="installmusic")],
            [InlineKeyboardButton(i18n.t(uid, "• پیکربندی", "• Configure"), callback_data="config")],
            [InlineKeyboardButton(i18n.t(uid, "• تنظیم شارژ", "• Set Charge"), callback_data="charge"),
             InlineKeyboardButton(i18n.t(uid, "• افزودن هلپر", "• Add Helper"), callback_data="addcli")],
            [InlineKeyboardButton(i18n.t(uid, "• بستن پنل", "• Close Panel"), callback_data="closepannel")],
        ]
    )


async def _notify_charge(client, m, kind_text, months):
    try:
        chat = await client.get_chat(m.message.chat.id)
        reqme = await client.get_me()
        uname = ("@" + reqme.username) if reqme.username else "ندارد !"
        text = (
            f"**⇐یک گروه به مدت {months} ماه برای قابلیت {kind_text} شارژ شد !**\n\n"
            f"◂ تاریخ : {utils.jalali_now()}\n"
            f"┈┅┅━━| **مشخصات گروه** |━━┅┅┈\n"
            f"◂ نام گروه : `{m.message.chat.title}`\n"
            f"◂ شناسه گروه : `{m.message.chat.id}`\n"
            f"◂ لینک گروه : [برای ورود به گروه کلیک کنید.]({chat.invite_link})\n"
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


async def _do_charge(client, m: CallbackQuery, months: int, kind: str):
    """kind '1' -> video (charge2/gp status 1), '2' -> music (charge/gp status 0)."""
    uid = m.from_user.id
    chat_id = m.message.chat.id
    days = {1: 30, 2: 60, 3: 90, 4: 120}[months]
    kind_text = i18n.t(uid, "پخش ویدیو", "video playback") if kind == "1" else i18n.t(uid, "پخش موزیک", "music playback")
    table = "charge2" if kind == "1" else "charge"
    gp_status = 1 if kind == "1" else 0

    # find the group owner
    owners = []
    try:
        async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if member.status == enums.ChatMemberStatus.OWNER and member.user:
                owners.append(member.user.id)
    except Exception:
        pass
    if not owners:
        await m.edit_message_text(
            i18n.t(uid, "• مالک گروه یافت نشد لطفا گروه را بصورت دستوری از طریق پی وی ربات نصب نمایید !", "• Group owner not found - please install the group via the bot's private chat !")
        )
        return

    if database.query(f"SELECT idgp FROM {table} WHERE idgp=?", (chat_id,)) != []:
        return await m.edit_message_text(
            i18n.t(uid, "• این گروه از قبل در لیست گروه های نصب شده موجود میباشد !", "• This group is already in the installed list !"),
            reply_markup=panel_markup(uid),
        )

    req = await client.get_chat(chat_id)
    now = time.time()
    database.execute(
        f"INSERT INTO {table}(idgp,idadmin,day,start,end,status,link,name) VALUES(?,?,?,?,?,?,?,?)",
        (chat_id, owners[0], days, now, now + float(days * 24 * 60 * 60), 0, req.invite_link, m.message.chat.title),
    )
    if database.query("SELECT creator FROM creators WHERE idgp=? AND creator=?", (chat_id, owners[0])) == []:
        database.execute("INSERT INTO creators(idgp, creator) VALUES(?,?)", (chat_id, owners[0]))
    if database.query("SELECT idgp FROM gp WHERE idgp=? AND status=?", (chat_id, gp_status)) == []:
        database.execute("INSERT INTO gp(namegp, idgp, linkgp, status) VALUES(?,?,?,?)",
                         (m.message.chat.title, chat_id, req.invite_link, gp_status))

    await m.edit_message_text(
        i18n.t(uid, f"• ربات با موفقیت برای {months} ماه استفاده از قابلیت {kind_text} شارژ شد !", f"• The bot was charged for {months} month(s) of {kind_text} !"),
        reply_markup=panel_markup(uid),
    )
    await _notify_charge(client, m, kind_text, months)


# ======================================================================
# Main panel entry callbacks
# ======================================================================
async def handle_panel(client, m: CallbackQuery, data: str):
    uid = m.from_user.id
    chat_id = m.message.chat.id

    if data == "closepannel":
        await m.edit_message_text(i18n.t(uid, "• پنل با موفقیت بسته شد !", "• The panel was closed successfully !"))
        return True

    if data == "installvideo":
        try:
            if m.message.chat.invite_link == "" and m.message.chat.username == "":
                return await m.edit_message_text(
                    i18n.t(uid, "• لطفا ابتدا ربات ها را در گروه ادمین کنید :", "• Please make the bots admins in the group first :"),
                    reply_markup=panel_markup(uid),
                )
        except AttributeError:
            pass
        if database.query("SELECT idgp FROM gp WHERE idgp=? AND status=1", (chat_id,)) != []:
            return await m.edit_message_text(
                i18n.t(uid, "• گروه شما از قبل در لیست گروه های ویدیو وجود داشت !", "• Your group is already in the video groups list !"),
                reply_markup=panel_markup(uid),
            )
        x = database.query("SELECT * FROM gp WHERE status=1")
        limit_rows = database.query("SELECT status,count FROM limmit")
        if limit_rows and limit_rows[0][0] == 1 and len(x) > limit_rows[0][1]:
            return await m.edit_message_text(
                i18n.t(uid, f"شما ظرفیت {limit_rows[0][1]} عددی خود را تکمیل کرده اید، لطفا یکی از گروه های قبلی را حذف کنید و دوباره تلاش کنید !",
                       f"You have reached your capacity of {limit_rows[0][1]} groups. Delete one and try again !")
            )
        link = m.message.chat.invite_link or m.message.chat.username
        database.execute("INSERT INTO gp(namegp, idgp, linkgp, status) VALUES(?,?,?,?)",
                         (m.message.chat.title, chat_id, link, 1))
        await m.edit_message_text(
            i18n.t(uid, "• گروه شما با موفقیت به لیست گروه های ویدیو اضافه شد !", "• Your group was added to the video groups list !"),
            reply_markup=panel_markup(uid),
        )
        await _notify_install(client, m, "گروه ویدیو")
        return True

    if data == "installmusic":
        try:
            if m.message.chat.invite_link == "" and m.message.chat.username == "":
                return await m.edit_message_text(i18n.t(uid, "• لطفا ابتدا ربات ها را در گروه ادمین نمایید !", "• Please make the bots admins in the group first !"))
        except AttributeError:
            pass
        if database.query("SELECT idgp FROM gp WHERE idgp=? AND status=0", (chat_id,)) != []:
            return await m.edit_message_text(
                i18n.t(uid, "• گروه شما از قبل در لیست گروه های موزیک وجود داشت !", "• Your group is already in the music groups list !"),
                reply_markup=panel_markup(uid),
            )
        x = database.query("SELECT * FROM gp WHERE status=0")
        limit_rows = database.query("SELECT status,count FROM limmit")
        if limit_rows and limit_rows[0][0] == 1 and len(x) > limit_rows[0][1]:
            return await m.edit_message_text(
                i18n.t(uid, f"شما ظرفیت {limit_rows[0][1]} عددی خود را تکمیل کرده اید، لطفا یکی از گروه های قبلی را حذف کنید و دوباره تلاش کنید !",
                       f"You have reached your capacity of {limit_rows[0][1]} groups. Delete one and try again !")
            )
        link = m.message.chat.invite_link or m.message.chat.username
        database.execute("INSERT INTO gp(namegp, idgp, linkgp, status) VALUES(?,?,?,?)",
                         (m.message.chat.title, chat_id, link, 0))
        await m.edit_message_text(
            i18n.t(uid, "• گروه شما با موفقیت به لیست گروه های موزیک اضافه شد !", "• Your group was added to the music groups list !"),
            reply_markup=panel_markup(uid),
        )
        await _notify_install(client, m, "گروه موزیک")
        return True

    if data == "config":
        await m.edit_message_text(
            i18n.t(uid, "• یکی از گزینه های زیر را برای پیکربندی انتخاب نمایید :", "• Choose one of the options below to configure :"),
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(i18n.t(uid, "• پیکربندی ویدیو", "• Configure Video"), callback_data="configvid"),
                     InlineKeyboardButton(i18n.t(uid, "• پیکربندی موزیک", "• Configure Music"), callback_data="configmus")],
                    [InlineKeyboardButton(i18n.t(uid, "• بازگشت", "• Back"), callback_data="back1")],
                ]
            ),
        )
        return True

    if data == "configvid":
        if database.query("SELECT idgp FROM gp WHERE status=1 AND idgp=?", (chat_id,)) == []:
            return await m.edit_message_text(i18n.t(uid, "• گروه ویدیو نصب نشده است !", "• The video group is not installed !"))
        async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if member.user is None:
                continue
            if database.query("SELECT idadmin FROM videoadmins WHERE idgp=? AND idadmin=?", (chat_id, member.user.id)) == []:
                database.execute("INSERT INTO videoadmins(idgp, idadmin, nameadmin) VALUES(?,?,?)",
                                 (chat_id, member.user.id, member.user.first_name))
        await m.edit_message_text(
            i18n.t(uid, "**⌯** تمامی مدیران با موفقیت شناسایی و در بخش ویدیو ربات ترفیع یافتند **!**", "**⌯** All admins were detected and promoted in the video section **!**"),
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(i18n.t(uid, "• پیکربندی ویدیو", "• Configure Video"), callback_data="configvid"),
                     InlineKeyboardButton(i18n.t(uid, "• پیکربندی موزیک", "• Configure Music"), callback_data="configmus")],
                    [InlineKeyboardButton(i18n.t(uid, "• بازگشت", "• Back"), callback_data="back1")],
                ]
            ),
        )
        return True

    if data == "configmus":
        if database.query("SELECT idgp FROM gp WHERE status=0 AND idgp=?", (chat_id,)) == []:
            return await m.edit_message_text(i18n.t(uid, "• گروه موزیک نصب نشده است !", "• The music group is not installed !"))
        async for member in client.get_chat_members(chat_id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if member.user is None:
                continue
            if database.query("SELECT idadmin FROM musicadmin WHERE idgp=? AND idadmin=?", (chat_id, member.user.id)) == []:
                database.execute("INSERT INTO musicadmin(idgp, idadmin, nameadmin) VALUES(?,?,?)",
                                 (chat_id, member.user.id, member.user.first_name))
        await m.edit_message_text(
            i18n.t(uid, "**⌯** تمامی مدیران با موفقیت شناسایی و در بخش موزیک ربات ترفیع یافتند **!**", "**⌯** All admins were detected and promoted in the music section **!**"),
            reply_markup=InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton(i18n.t(uid, "• پیکربندی ویدیو", "• Configure Video"), callback_data="configvid"),
                     InlineKeyboardButton(i18n.t(uid, "• پیکربندی موزیک", "• Configure Music"), callback_data="configmus")],
                    [InlineKeyboardButton(i18n.t(uid, "• بازگشت", "• Back"), callback_data="back1")],
                ]
            ),
        )
        return True

    if data == "charge":
        await m.edit_message_text(
            i18n.t(uid, "• یکی از گزینه های زیر را انتخاب نمایید :", "• Choose one of the options below :"),
            reply_markup=utils.charge_menu_keyboard(uid),
        )
        return True

    if data == "chargevideo":
        await m.edit_message_text(
            i18n.t(uid, "• مدت زمان اشتراک مورد نظر ربات را برای قابلیت پخش ویدیو انتخاب نمایید :", "• Choose the subscription period for video playback :"),
            reply_markup=utils.months_keyboard(uid, "1"),
        )
        return True

    if data == "chargemusic":
        await m.edit_message_text(
            i18n.t(uid, "• مدت زمان اشتراک مورد نظر ربات را برای قابلیت پخش موزیک انتخاب نمایید :", "• Choose the subscription period for music playback :"),
            reply_markup=utils.months_keyboard(uid, "2"),
        )
        return True

    if data in ("1mah1", "2mah1", "3mah1", "4mah1"):
        await _do_charge(client, m, int(data[0]), "1")
        return True

    if data in ("1mah2", "2mah2", "3mah2", "4mah2"):
        await _do_charge(client, m, int(data[0]), "2")
        return True

    if data == "back1":
        await m.edit_message_text(
            i18n.t(uid, "• یکی از گزینه های زیر را انتخاب نمایید :", "• Choose one of the options below :"),
            reply_markup=panel_markup(uid),
        )
        return True

    if data == "back2":
        await m.edit_message_text(
            i18n.t(uid, "• یکی از گزینه های زیر را انتخاب نمایید :", "• Choose one of the options below :"),
            reply_markup=utils.charge_menu_keyboard(uid),
        )
        return True

    if data == "addcli":
        if database.query("SELECT idgp FROM gp WHERE idgp=?", (chat_id,)) == []:
            return await m.edit_message_text(i18n.t(uid, "• لطفا ابتدا گروه را نصب کنید !", "• Please install the group first !"))
        if not helper_session_exists():
            return await m.edit_message_text(i18n.t(uid, "• حساب هلپر وارد نشده است ! لطفا ابتدا /login را انجام دهید.", "• The helper account is not logged in ! Please run /login first."))
        try:
            await ubot.send_message(chat_id, i18n.t(uid, "• ربات هلپر عضو گروه میباشد !", "• The helper bot is already a member of the group !"))
            return True
        except Exception:
            pass
        try:
            linkgp = await client.export_chat_invite_link(chat_id)
        except Exception:
            return await m.message.reply(i18n.t(uid, "• لطفا ربات را در گروه ادمین کنید !", "• Please make the bot an admin in the group !"))
        try:
            await ubot.join_chat(linkgp)
        except Exception:
            pass
        try:
            reqme = await ubot.get_me()
            await app.promote_chat_member(
                chat_id=chat_id, user_id=reqme.id,
                privileges=ChatPrivileges(
                    can_delete_messages=True,
                    can_pin_messages=True,
                    can_invite_users=True,
                    can_manage_video_chats=True,
                ),
            )
            await ubot.send_message(chat_id, i18n.t(uid, "• هلپر با موفقیت جوین شد !", "• The helper joined successfully !"))
        except Exception:
            return await ubot.send_message(chat_id, i18n.t(uid, "لطفا ربات را در گروه ادمین کنید !", "Please make the bot an admin in the group !"))
        return True

    if data in ("delmus", "delvid", "delboth"):
        if data in ("delmus", "delboth"):
            database.execute("DELETE FROM musicadmin WHERE idgp=?", (chat_id,))
            database.execute("DELETE FROM gp WHERE idgp=? AND status=0", (chat_id,))
            database.execute("DELETE FROM charge WHERE idgp=?", (chat_id,))
        if data in ("delvid", "delboth"):
            database.execute("DELETE FROM videoadmins WHERE idgp=?", (chat_id,))
            database.execute("DELETE FROM gp WHERE idgp=? AND status=1", (chat_id,))
            database.execute("DELETE FROM charge2 WHERE idgp=?", (chat_id,))
        for target in (SUDO, OWNER):
            try:
                await app.send_message(target, f"دیتای گروه {m.message.chat.title} توسط {m.from_user.mention(m.from_user.first_name)} کاملا حذف شد !")
            except Exception:
                pass
        await m.edit_message_text(
            i18n.t(uid, f"• تمام دیتاهای مربوط به گروه {m.message.chat.title} حذف شد ! ", f"• All data of {m.message.chat.title} was deleted ! "),
            reply_markup=utils.delete_keyboard(uid),
        )
        return True

    if data == "left":
        await m.edit_message_text(i18n.t(uid, "**⌯** ربات از این گروه خارج میشود **!**", "**⌯** The bot is leaving this group **!**"))
        try:
            req = await client.get_chat(chat_id)
            for target in (SUDO, OWNER):
                try:
                    await client.send_message(
                        target,
                        f"**⇐ یکی از سودو ها دستور لفت را استفاده کرد !**\n\n"
                        f"◂ تاریخ : {utils.jalali_now()}\n"
                        f"┈┅┅━━| **مشخصات گروه** |━━┅┅┈\n"
                        f"◂ نام گروه : `{m.message.chat.title}`\n"
                        f"◂ شناسه گروه : `{m.message.chat.id}`\n"
                        f"◂ لینک گروه : [برای ورود به گروه کلیک کنید.]({req.invite_link})\n"
                        f"┈┅┅━━| **مشخصات همکار** |━━┅┅┈\n"
                        f"◂ نام : `{m.from_user.first_name}`\n"
                        f"◂ یوزرنیم : @{m.from_user.username}\n"
                        f"◂ آیدی عددی : `{m.from_user.id}`",
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass
        except Exception:
            pass
        await app.leave_chat(chat_id)
        if helper_session_exists():
            try:
                await ubot.leave_chat(chat_id)
            except Exception:
                pass
        return True

    if data == "closedel":
        await m.message.delete()
        await m.answer(i18n.t(uid, "پنل با موفقیت بسته شد !", "The panel was closed successfully !"), show_alert=True)
        return True

    return False


async def _notify_install(client, m, kind_text):
    try:
        req = await client.get_chat(m.message.chat.id)
        reqme = await client.get_me()
        uname = ("@" + reqme.username) if reqme.username else "ندارد !"
        text = (
            f"**⇐یک {kind_text} نصب شد !**\n\n"
            f"◂ تاریخ : {utils.jalali_now()}\n"
            f"┈┅┅━━| **مشخصات گروه** |━━┅┅┈\n"
            f"◂ نام گروه : `{m.message.chat.title}`\n"
            f"◂ شناسه گروه : `{m.message.chat.id}`\n"
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
