"""
Owner / sudo admin panel (private chat) - reply-keyboard buttons.

The button layout and behavior are kept identical to the original bot.
"""
import time

from pyrogram import filters
from pyrogram.types import Message
from pyrogram.errors.exceptions.bad_request_400 import MessageEmpty

import config
import convo
import database
import i18n
import utils
from clients import app

cfg = config.get_config()

OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID


def _panel_allow(uid):
    return uid in (OWNER, SUDO, *database.idsudos(), *database.idowner())


# ----------------------------------------------------------------------
# 📊 وضعیت - status
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^(📊 وضعیت)$"))
async def vaziat(client, m: Message):
    uid = m.from_user.id
    vidactive = len(database.kir(0))
    vidtam = len(database.kir(1))
    musactive = len(database.moz(0))
    mustam = len(database.moz(1))
    allvaz = len([*database.moz(2), *database.kir(2)])

    muscount = len(database.insmusic())
    vidcount = len(database.insvideo())

    left_rows = database.query("SELECT status FROM autoleft")
    left = "تعریف نشده" if left_rows == [] else ("فعال" if int(left_rows[0][0]) == 1 else "غیرفعال")

    ch_rows = database.channel()
    chan = "تعریف نشده" if ch_rows == [] else ("فعال" if int(ch_rows[0][3]) == 1 else "غیرفعال")

    fa = (
        f"◄ وضعیت و آمار ربات :\n\n"
        f"◂ آیدی عددی مدیر کل : {uid}\n\n"
        f"─┅━ **آمار گروه ها** ━┅─\n\n"
        f"◂ تعداد گروه تحت مدیریت موزیک : {musactive}\n\n"
        f"◂ تعداد گروه تحت مدیریت ویدیو : {vidactive}\n\n"
        f"◂ تعداد گروه تمدید موزیک : {mustam}\n\n"
        f"◂ تعداد گروه تمدید ویدیو : {vidtam}\n\n"
        f"◂ تعداد گروه بدون اعتبار : {allvaz}\n\n"
        f"─┅━ **تنظیمات ربات** ━┅─\n\n"
        f"◂ اجبار ورود : {chan}\n\n"
        f"◂ خروج خودکار : {left}"
    )
    en = (
        f"◄ Bot status & statistics :\n\n"
        f"◂ Master admin id : {uid}\n\n"
        f"─┅━ **Groups** ━┅─\n\n"
        f"◂ Music groups : {musactive}\n\n"
        f"◂ Video groups : {vidactive}\n\n"
        f"◂ Music groups to renew : {mustam}\n\n"
        f"◂ Video groups to renew : {vidtam}\n\n"
        f"◂ Groups without credit : {allvaz}\n\n"
        f"─┅━ **Settings** ━┅─\n\n"
        f"◂ Force join : {chan}\n\n"
        f"◂ Auto leave : {left}"
    )
    await m.reply(i18n.t(uid, fa, en))


# ----------------------------------------------------------------------
# ▪️/▫️ خروج خودکار - auto leave toggle
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^(▪️ خروج خودکار فعال)$"))
async def autoleft_on(client, m: Message):
    uid = m.from_user.id
    rows = database.query("SELECT status FROM autoleft")
    if rows == []:
        database.execute("INSERT INTO autoleft(status) VALUES(?)", (1,))
    else:
        database.execute("UPDATE autoleft SET status=1")
    await m.reply(i18n.t(uid, "• خروج خودکار فعال شد !", "• Auto-leave enabled !"))


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^(▫️ خروج خودکار غیرفعال)$"))
async def autoleft_off(client, m: Message):
    uid = m.from_user.id
    rows = database.query("SELECT status FROM autoleft")
    if rows == []:
        database.execute("INSERT INTO autoleft(status) VALUES(?)", (0,))
    else:
        database.execute("UPDATE autoleft SET status=0")
    await m.reply(i18n.t(uid, "• خروج خودکار غیرفعال شد !", "• Auto-leave disabled !"))


# ----------------------------------------------------------------------
# تنظیم محدودیت 🔏 / محدودیت نصب فعال/غیرفعال (owner only)
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^(تنظیم محدودیت 🔏)$"))
async def set_limit(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "• مقدار مورد نظر جهت محدودیت نصب را وارد کنید !", "• Enter the install limit value !"))

    async def _got(client, msg, data):
        try:
            value = int(msg.text)
        except ValueError:
            return await msg.reply(i18n.t(uid, "• لطفا یک عدد وارد کنید !", "• Please enter a number !"))
        rows = database.query("SELECT status,count FROM limmit")
        if rows != []:
            database.execute("UPDATE limmit SET count=?", (value,))
        else:
            database.execute("INSERT INTO limmit(status,count) VALUES(?,?)", (0, value))
        await msg.reply(i18n.t(uid, "• مقدار محدودیت با موفقیت تنظیم شد !", "• Install limit set !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^(محدودیت نصب فعال ⚠️)$"))
async def limit_on(client, m: Message):
    uid = m.from_user.id
    rows = database.query("SELECT status,count FROM limmit")
    if rows != []:
        database.execute("UPDATE limmit SET status=1")
    else:
        database.execute("INSERT INTO limmit(status,count) VALUES(?,?)", (1, 30))
    await m.reply(i18n.t(uid, "• محدودیت با موفقیت فعال شد !", "• Install limit enabled !"))


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^(محدودیت نصب غیرفعال ♻️)$"))
async def limit_off(client, m: Message):
    uid = m.from_user.id
    rows = database.query("SELECT status,count FROM limmit")
    if rows != []:
        database.execute("UPDATE limmit SET status=0")
    else:
        database.execute("INSERT INTO limmit(status,count) VALUES(?,?)", (0, 30))
    await m.reply(i18n.t(uid, "• محدودیت با موفقیت غیرفعال شد !", "• Install limit disabled !"))


# ----------------------------------------------------------------------
# 📨 ارسال همگانی - broadcast (users / groups)
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📨 ارسال همگانی گروه ها$"))
async def broadcast_groups(client, m: Message):
    uid = m.from_user.id
    await m.reply(
        i18n.t(
            uid,
            "◂ عبارت مورد نیاز جهت ارسال به تمام گروه‌ها را ارسال کنید (جهت لغو از /cancel استفاده کنید !)",
            "◂ Send the message to broadcast to all groups (send /cancel to abort !)",
        )
    )

    async def _got(client, msg, data):
        kh = await msg.reply(
            i18n.t(uid, "• در حال ارسال متن به تمامی گروه ها ...\n◂ چند دقیقه منتظر بمانید !", "• Sending to all groups ...\n◂ Please wait a few minutes !")
        )
        ok = 0
        for i in database.query("SELECT idgp FROM charge"):
            try:
                await client.copy_message(i[0], msg.chat.id, msg.id)
                ok += 1
            except Exception:
                pass
        for ii in database.query("SELECT idgp FROM charge2"):
            try:
                await client.copy_message(ii[0], msg.chat.id, msg.id)
                ok += 1
            except Exception:
                pass
        await kh.edit(
            i18n.t(uid, f"• متن مورد نظر به {ok} گروه ارسال شد !", f"• Message sent to {ok} groups !")
        )

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📨 ارسال همگانی$"))
async def broadcast_users(client, m: Message):
    uid = m.from_user.id
    await m.reply(
        i18n.t(
            uid,
            "◂ مورد مورد نظر برای ارسال همگانی را وارد کنید و برای لغو از /cancel استفاده کنید :",
            "◂ Enter the message to broadcast to all users (send /cancel to abort) :",
        )
    )

    async def _got(client, msg, data):
        kh = await msg.reply(
            i18n.t(uid, "• در حال ارسال به تمامی کاربران ...\n◂ چند دقیقه منتظر بمانید !", "• Sending to all users ...\n◂ Please wait a few minutes !")
        )
        ok = 0
        for i in database.readusers():
            try:
                await client.copy_message(i, msg.chat.id, msg.id)
                ok += 1
            except Exception:
                pass
        await kh.edit(
            i18n.t(uid, f"• به {ok} کاربر ارسال شد !", f"• Sent to {ok} users !")
        )

    convo.ask(uid, _got)


# ----------------------------------------------------------------------
# ▪️/▫️ اجبار ورود - force join toggle
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user([OWNER, SUDO]) & (filters.regex(r"^▪️اجبار ورود فعال$") | filters.regex(r"^([Jj][Oo][Ii][Nn][Oo][Nn])$")))
async def join_on(client, m: Message):
    uid = m.from_user.id
    ch_rows = database.channel()
    if ch_rows == [] or ch_rows[0][0] is None:
        return await m.reply(i18n.t(uid, "• لطفا ابتدا یک کانال برای این بخش تنظیم کنید !", "• Please set a channel first !"))
    database.execute("UPDATE channel SET status=1")
    await m.reply(i18n.t(uid, "• اجبار ورود فعال شد !", "• Force-join enabled !"))


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & (filters.regex(r"^▫️اجبار ورود غیرفعال$") | filters.regex(r"^([Jj][Oo][Ii][Nn][Oo][Ff][Ff])$")))
async def join_off(client, m: Message):
    uid = m.from_user.id
    ch_rows = database.channel()
    if ch_rows == [] or ch_rows[0][0] is None:
        return await m.reply(i18n.t(uid, "• لطفا ابتدا یک کانال برای این بخش تنظیم کنید !", "• Please set a channel first !"))
    database.execute("UPDATE channel SET status=0")
    await m.reply(i18n.t(uid, "• اجبار ورود غیرفعال شد !", "• Force-join disabled !"))


# ----------------------------------------------------------------------
# Group list helpers
# ----------------------------------------------------------------------
def _fmt_charge_list(rows, unit_day: bool):
    charlist = ""
    count = 0
    for i in rows:
        count += 1
        remaining = int(i[4] - time.time())
        if unit_day:
            remaining = int(remaining / 60 / 60 / 24)
            unit = "روز" if i18n.lang_of(0) == "fa" else "days"
        else:
            remaining = int(remaining / 60 / 60)
            unit = "ساعت" if i18n.lang_of(0) == "fa" else "hours"
        charlist += (
            f"{count} - {i[7]}\n"
            f"◂ شناسه گروه : `{i[0]}`\n"
            f"◂ لینک گروه : [برای ورود کلیک کنید.]({i[6]})\n"
            f"◂ اعتبار : `{remaining}` {unit}\n"
            f"─┅━━━━━━━━✥━━━━━━━━┅─\n"
        )
    return charlist


async def _send_chunked(client, m, text, empty_msg):
    if not text.strip():
        return await m.reply(empty_msg)
    # split into <=4000 chunks
    chunks = [text[i:i + 4000] for i in range(0, len(text), 4000)]
    for c in chunks:
        try:
            await m.reply(c, disable_web_page_preview=True)
        except MessageEmpty:
            pass


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📋 لیست گروه های فعال موزیک$"))
async def list_music_active(client, m: Message):
    uid = m.from_user.id
    rows = database.query("SELECT * FROM charge WHERE status=0")
    text = _fmt_charge_list(rows, unit_day=True)
    await _send_chunked(client, m, text, i18n.t(uid, "• در حال حاضر گروه فعالی ثبت نشده است !", "• No active groups registered !"))


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📁 لیست گروه های تمدید موزیک$"))
async def list_music_renew(client, m: Message):
    uid = m.from_user.id
    rows = database.query("SELECT * FROM charge WHERE status=1")
    text = _fmt_charge_list(rows, unit_day=False)
    await _send_chunked(client, m, text, i18n.t(uid, "• در حال حاضر گروه تمدیدی ثبت نشده است !", "• No groups to renew !"))


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📋 لیست گروه های فعال ویدیو$"))
async def list_video_active(client, m: Message):
    uid = m.from_user.id
    rows = database.query("SELECT * FROM charge2 WHERE status=0")
    text = _fmt_charge_list(rows, unit_day=True)
    await _send_chunked(client, m, text, i18n.t(uid, "• در حال حاضر گروه فعالی ثبت نشده است !", "• No active groups registered !"))


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📁 لیست گروه های تمدید ویدیو$"))
async def list_video_renew(client, m: Message):
    uid = m.from_user.id
    rows = database.query("SELECT * FROM charge2 WHERE status=1")
    text = _fmt_charge_list(rows, unit_day=False)
    await _send_chunked(client, m, text, i18n.t(uid, "• در حال حاضر گروه تمدیدی ثبت نشده است !", "• No groups to renew !"))


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^⚠️ لیست گروه های فاقد اعتبار$"))
async def list_no_credit(client, m: Message):
    uid = m.from_user.id
    charlist = ""
    count = 0
    for i in database.query("SELECT * FROM charge WHERE status=2"):
        count += 1
        charlist += f"{count} - {i[7]} (#Music)\n◂ شناسه گروه : `{i[0]}`\n◂ لینک گروه : [برای ورود کلیک کنید.]({i[6]})\n─┅━━━━━━━━✥━━━━━━━━┅─\n"
    for i in database.query("SELECT * FROM charge2 WHERE status=2"):
        count += 1
        charlist += f"{count} - {i[7]} (#Video)\n◂ شناسه گروه : `{i[0]}`\n◂ لینک گروه : [برای ورود کلیک کنید.]({i[6]})\n─┅━━━━━━━━✥━━━━━━━━┅─\n"
    await _send_chunked(client, m, charlist, i18n.t(uid, "• در حال حاضر گروه فاقد اعتباری ثبت نشده است !", "• No groups without credit !"))


# ----------------------------------------------------------------------
# 📌 تنظیم سودو / ❌ حذف سودو (private)
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📌 تنظیم سودو$"))
async def add_sudo_pv(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**•** آیدی عددی کاربر مورد نظر را وارد کنید **:**", "**•** Enter the numeric id of the user **:**"))

    async def _got(client, msg, data):
        try:
            req = await client.get_chat(int(msg.text))
        except Exception:
            return await msg.reply(i18n.t(uid, "**•** کاربر مورد نظر یافت نشد **!**", "**•** User not found **!**"))
        if database.query("SELECT idsudo FROM sudo WHERE idsudo=?", (req.id,)) != []:
            return await msg.reply(i18n.t(uid, "• این کاربر از قبل در لیست سودو ها موجود میباشد !", "• This user is already a sudo !"))
        database.execute("INSERT INTO sudo(idsudo, namesudo) VALUES(?,?)", (req.id, req.first_name))
        uname = 'ندارد' if req.username is None else req.username
        await msg.reply(
            i18n.t(
                uid,
                f"**◆ یک کاربر با موفقیت به لیست سودو های ربات اضافه شد !**\n◂ نام سودو : **{req.first_name}**\n◂ شناسه سودو : `{req.id}`\n◂ یوزرنیم سودو : {uname}",
                f"**◆ User added to the sudo list !**\n◂ Name : **{req.first_name}**\n◂ Id : `{req.id}`\n◂ Username : {uname}",
            )
        )
        try:
            await client.send_message(req.id, i18n.t(req.id, "**⌯** شما به عنوان سودوی ربات منصوب شدید **!**", "**⌯** You have been appointed as bot sudo **!**"))
        except Exception:
            pass

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^❌ حذف سودو$"))
async def del_sudo_pv(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**⌯** آیدی عددی کاربر مورد نظر را وارد کنید **:**", "**⌯** Enter the numeric id of the user **:**"))

    async def _got(client, msg, data):
        try:
            req = await client.get_chat(int(msg.text))
        except Exception:
            return await msg.reply(i18n.t(uid, "**⌯** کاربر مورد نظر یافت نشد **!**", "**⌯** User not found **!**"))
        database.execute("DELETE FROM sudo WHERE idsudo=?", (req.id,))
        uname = 'ندارد' if req.username is None else req.username
        await msg.reply(
            i18n.t(
                uid,
                f"**◆ یک کاربر با موفقیت از لیست سودو های ربات حذف شد !**\n◂ نام سودو : **{req.first_name}**\n◂ شناسه سودو : `{req.id}`\n◂ یوزرنیم سودو : {uname}",
                f"**◆ User removed from the sudo list !**\n◂ Name : **{req.first_name}**\n◂ Id : `{req.id}`\n◂ Username : {uname}",
            )
        )
        try:
            await client.send_message(req.id, i18n.t(req.id, "**⌯** شما از لیست سودو های ربات حذف شدید **!**", "**⌯** You have been removed from the sudo list **!**"))
        except Exception:
            pass

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^👥 لیست سودو های ربات"))
async def sudo_list(client, m: Message):
    uid = m.from_user.id
    rows = database.query("SELECT idsudo,namesudo FROM sudo")
    if not rows:
        return await m.reply(i18n.t(uid, "**◂ لیست سودو های ربات خالی میباشد !**", "**◂ The sudo list is empty !**"))
    text = ""
    for r in rows:
        try:
            chat = await client.get_chat(r[0])
            uname = f"@{chat.username}" if chat.username else "—"
        except Exception:
            uname = "—"
        text += f"◂ نام سودو : {r[1]}\n◂ شناسه سودو : {r[0]}\n◂ یوزرنیم سودو : {uname}\n\n"
    await m.reply(text)


# ----------------------------------------------------------------------
# 📌 تنظیم ادمین / ❌ حذف ادمین (private) -> owner table
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📌 تنظیم ادمین$"))
async def add_admin_pv(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**⌯** آیدی عددی کاربر مورد نظر را وارد کنید **:**", "**⌯** Enter the numeric id of the user **:**"))

    async def _got(client, msg, data):
        try:
            req = await client.get_chat(int(msg.text))
        except Exception:
            return await msg.reply(i18n.t(uid, "**⌯** کاربر مورد نظر یافت نشد **!**", "**⌯** User not found **!**"))
        if database.query("SELECT idowner FROM owner WHERE idowner=?", (req.id,)) != []:
            return await msg.reply(i18n.t(uid, "• این کاربر از قبل در لیست ادمین ها موجود میباشد !", "• This user is already an admin !"))
        database.execute("INSERT INTO owner(idowner, nameowner) VALUES(?,?)", (req.id, req.first_name))
        uname = 'ندارد' if req.username is None else req.username
        await msg.reply(
            i18n.t(
                uid,
                f"• یک کاربر با موفقیت به لیست ادمین های ربات اضافه شد !\n◂ نام ادمین : **{req.first_name}**\n◂ شناسه ادمین : `{req.id}`\n◂ یوزرنیم ادمین : {uname}",
                f"• User added to the admin list !\n◂ Name : **{req.first_name}**\n◂ Id : `{req.id}`\n◂ Username : {uname}",
            )
        )
        try:
            await client.send_message(req.id, i18n.t(req.id, "**⌯** شما به عنوان ادمین ربات منصوب شدید **!**", "**⌯** You have been appointed as bot admin **!**"))
        except Exception:
            pass

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^❌ حذف ادمین$"))
async def del_admin_pv(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**⌯** آیدی عددی کاربر مورد نظر را وارد کنید **:**", "**⌯** Enter the numeric id of the user **:**"))

    async def _got(client, msg, data):
        try:
            req = await client.get_chat(int(msg.text))
        except Exception:
            return await msg.reply(i18n.t(uid, "**⌯** کاربر مورد نظر یافت نشد **!**", "**⌯** User not found **!**"))
        database.execute("DELETE FROM owner WHERE idowner=?", (req.id,))
        uname = 'ندارد' if req.username is None else req.username
        await msg.reply(
            i18n.t(
                uid,
                f"• یک کاربر با موفقیت از لیست ادمین های ربات حذف شد !\n◂ نام ادمین : **{req.first_name}**\n◂ شناسه ادمین : `{req.id}`\n◂ یوزرنیم ادمین : {uname}",
                f"• User removed from the admin list !\n◂ Name : **{req.first_name}**\n◂ Id : `{req.id}`\n◂ Username : {uname}",
            )
        )
        try:
            await client.send_message(req.id, i18n.t(req.id, "**⌯** شما از لیست ادمین های ربات حذف شدید **!**", "**⌯** You have been removed from the admin list **!**"))
        except Exception:
            pass

    convo.ask(uid, _got)


# ----------------------------------------------------------------------
# 🗑 حذف گروه موزیک/ویدیو (private)
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^🗑 حذف گروه موزیک$"))
async def del_group_music(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**⌯** شناسه ی گروه مورد نظر را وارد کنید **:**", "**⌯** Enter the group id **:**"))

    async def _got(client, msg, data):
        try:
            gid = int(msg.text)
        except ValueError:
            return await msg.reply(i18n.t(uid, "• لطفا شناسه را به صورت عدد وارد کنید !", "• Please enter a numeric id !"))
        database.execute("DELETE FROM musicadmin WHERE idgp=?", (gid,))
        database.execute("DELETE FROM gp WHERE idgp=? AND status=0", (gid,))
        database.execute("DELETE FROM charge WHERE idgp=?", (gid,))
        await msg.reply(i18n.t(uid, "• گروه مورد نظر با موفقیت حذف شد !", "• Group deleted successfully !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^🗑 حذف گروه ویدیو$"))
async def del_group_video(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**⌯** شناسه ی گروه مورد نظر را وارد کنید **:**", "**⌯** Enter the group id **:**"))

    async def _got(client, msg, data):
        try:
            gid = int(msg.text)
        except ValueError:
            return await msg.reply(i18n.t(uid, "• لطفا شناسه را به صورت عدد وارد کنید !", "• Please enter a numeric id !"))
        database.execute("DELETE FROM videoadmins WHERE idgp=?", (gid,))
        database.execute("DELETE FROM gp WHERE idgp=? AND status=1", (gid,))
        database.execute("DELETE FROM charge2 WHERE idgp=?", (gid,))
        await msg.reply(i18n.t(uid, "• گروه مورد نظر با موفقیت حذف شد !", "• Group deleted successfully !"))

    convo.ask(uid, _got)


# ----------------------------------------------------------------------
# 📬 ارسال به سودو (owner only)
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^📬 ارسال به سودو$"))
async def send_to_sudo(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "• پیام خود را به سودو ارسال کنید :", "• Send your message to the sudo :"))

    async def _got(client, msg, data):
        try:
            await client.send_message(SUDO, msg.text, disable_web_page_preview=True)
            await msg.reply(i18n.t(uid, "• پیام شما به سودو ارسال شد !", "• Your message was sent to the sudo !"))
        except Exception:
            await msg.reply(i18n.t(uid, "• ارسال پیام با مشکل مواجه شد !", "• Failed to send the message !"))

    convo.ask(uid, _got)


# ----------------------------------------------------------------------
# 📚 تنظیم درباره ما / ✏️ تنظیم استارت / ✏️ تنظیم استارت هلپر (owner)
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^📚 تنظیم درباره ما$"))
async def set_about(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "• متن جدید درباره ما را ارسال کنید :", "• Send the new about text :"))

    async def _got(client, msg, data):
        database.execute("UPDATE information SET about=? WHERE id=1", (msg.text,))
        await msg.reply(i18n.t(uid, "• درباره ما با موفقیت تنظیم شد !", "• About text updated !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^✏️ تنظیم استارت$"))
async def set_start(client, m: Message):
    uid = m.from_user.id
    await m.reply(
        i18n.t(
            uid,
            "• متن جدید استارت را ارسال کنید :\n`MENTION` = نام کاربر\n`BOLD` = **\n`USERID` = آیدی عددی",
            "• Send the new start text :\n`MENTION` = user mention\n`BOLD` = **\n`USERID` = numeric id",
        )
    )

    async def _got(client, msg, data):
        database.execute("UPDATE information SET start=? WHERE id=1", (msg.text,))
        await msg.reply(i18n.t(uid, "• استارت با موفقیت تنظیم شد !", "• Start text updated !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^✏️ تنظیم استارت هلپر$"))
async def set_start_helper(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "• متن جدید استارت هلپر را ارسال کنید :", "• Send the new helper start text :"))

    async def _got(client, msg, data):
        rows = database.query("SELECT start FROM startcli")
        if rows == []:
            database.execute("INSERT INTO startcli(start) VALUES(?)", (msg.text,))
        else:
            database.execute("UPDATE startcli SET start=?", (msg.text,))
        await msg.reply(i18n.t(uid, "• استارت هلپر با موفقیت تنظیم شد !", "• Helper start text updated !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^📥 تنظیم پی وی$"))
async def set_pv(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "• یوزرنیم (بدون @) را برای خرید مستقیم ارسال کنید :", "• Send the username (without @) for direct purchase :"))

    async def _got(client, msg, data):
        database.execute("UPDATE information SET adminpv=? WHERE id=1", (msg.text,))
        await msg.reply(i18n.t(uid, "• پی وی با موفقیت تنظیم شد !", "• Direct-purchase username updated !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^📬 تنظیم پیامرسان$"))
async def set_payamresan(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "• یوزرنیم (بدون @) پیامرسان را ارسال کنید :", "• Send the messenger username (without @) :"))

    async def _got(client, msg, data):
        database.execute("UPDATE information SET payamresan=? WHERE id=1", (msg.text,))
        await msg.reply(i18n.t(uid, "• پیامرسان با موفقیت تنظیم شد !", "• Messenger updated !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^👥 تنظیم گروه$"))
async def set_group(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**◆ لینک گروه را بدون `https://t.me/` وارد کنید :**", "**◆ Send the group link without `https://t.me/` :**"))

    async def _got(client, msg, data):
        database.execute("UPDATE information SET groupp=? WHERE id=1", (msg.text,))
        await msg.reply(i18n.t(uid, "**◆ لینک گروه با موفقیت ست شد ✓**", "**◆ Group link set ✓**"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^📢 تنظیم کانال$"))
async def set_channel(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "• آیدی عددی کانال را همراه با -100 وارد کنید :", "• Enter the channel numeric id (with -100) :"))

    async def _got(client, msg, data):
        try:
            req = await client.get_chat(int(msg.text))
        except Exception:
            return await msg.reply(i18n.t(uid, "• کانال یافت نشد !", "• Channel not found !"))
        if req.invite_link is None:
            return await msg.reply(i18n.t(uid, "• ربات در کانال ادمین نیست !", "• The bot is not an admin of the channel !"))
        rows = database.channel()
        if rows == []:
            database.execute(
                "INSERT INTO channel(idchannel, namechannel, invite, status) VALUES(?,?,?,?)",
                (req.id, req.title, req.invite_link, 0),
            )
        else:
            database.execute(
                "UPDATE channel SET idchannel=?, namechannel=?, invite=? WHERE idchannel=?",
                (req.id, req.title, req.invite_link, rows[0][0]),
            )
        await msg.reply(i18n.t(uid, f"• کانال {req.title} با موفقیت تنظیم شد !", f"• Channel {req.title} set !"))

    convo.ask(uid, _got)


# ----------------------------------------------------------------------
# Rate settings (money1 / paye)
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^نرخ فروش موزیک$"))
async def rate_music_sale(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**نرخ پرداختی گروه ها را برای صاحب گروه ها به ازای هر گروه موزیک وارد کنید :\nبرای مثال (20000) به معنی 20 هزار تومان**", "**Enter the price per music group (for group owners) :\nExample (20000) means 20,000 toman**"))

    async def _got(client, msg, data):
        try:
            value = int(msg.text)
        except ValueError:
            return await msg.reply(i18n.t(uid, "• لطفا یک عدد وارد کنید !", "• Please enter a number !"))
        database.execute("UPDATE money1 SET nerkh1=? WHERE kos=1", (value,))
        await msg.reply(i18n.t(uid, "• نرخ جدید با موفقیت ثبت شد !", "• New rate saved !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^نرخ فروش ویدیو$"))
async def rate_video_sale(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**نرخ پرداختی گروه ها را برای صاحب گروه ها به ازای هر گروه ویدیو وارد کنید :\nبرای مثال (30000) به معنی 30 هزار تومان**", "**Enter the price per video group (for group owners) :\nExample (30000) means 30,000 toman**"))

    async def _got(client, msg, data):
        try:
            value = int(msg.text)
        except ValueError:
            return await msg.reply(i18n.t(uid, "• لطفا یک عدد وارد کنید !", "• Please enter a number !"))
        database.execute("UPDATE money1 SET nerkh2=? WHERE kos=1", (value,))
        await msg.reply(i18n.t(uid, "• نرخ جدید با موفقیت ثبت شد !", "• New rate saved !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^تنظیم نرخ موزیک$"))
async def rate_music_sudo(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**نرخ پرداختی گروه ها را برای سودو ها به ازای هر گروه موزیک وارد کنید :\nبرای مثال (9000) به معنی 9 هزار تومان**", "**Enter the price per music group (for sudos) :\nExample (9000) means 9,000 toman**"))

    async def _got(client, msg, data):
        try:
            value = int(msg.text)
        except ValueError:
            return await msg.reply(i18n.t(uid, "• لطفا یک عدد وارد کنید !", "• Please enter a number !"))
        database.execute("UPDATE money1 SET nerkh1=? WHERE kos=2", (value,))
        await msg.reply(i18n.t(uid, "• نرخ جدید با موفقیت ثبت شد !", "• New rate saved !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^تنظیم نرخ ویدیو$"))
async def rate_video_sudo(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**نرخ پرداختی گروه ها را برای سودو ها به ازای هر گروه ویدیو وارد کنید :\nبرای مثال (15000) به معنی 15 هزار تومان**", "**Enter the price per video group (for sudos) :\nExample (15000) means 15,000 toman**"))

    async def _got(client, msg, data):
        try:
            value = int(msg.text)
        except ValueError:
            return await msg.reply(i18n.t(uid, "• لطفا یک عدد وارد کنید !", "• Please enter a number !"))
        database.execute("UPDATE money1 SET nerkh2=? WHERE kos=2", (value,))
        await msg.reply(i18n.t(uid, "• نرخ جدید با موفقیت ثبت شد !", "• New rate saved !"))

    convo.ask(uid, _got)


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^تنظیم نرخ پایه$"))
async def rate_base(client, m: Message):
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "**نرخ پرداختی پایه ربات را وارد کنید :\nبرای مثال (15000) به معنی 15 هزار تومان**", "**Enter the base rate of the bot :\nExample (15000) means 15,000 toman**"))

    async def _got(client, msg, data):
        try:
            value = int(msg.text)
        except ValueError:
            return await msg.reply(i18n.t(uid, "• لطفا یک عدد وارد کنید !", "• Please enter a number !"))
        database.execute("UPDATE paye SET nerkh=? WHERE kos=1", (value,))
        await msg.reply(i18n.t(uid, "• نرخ جدید با موفقیت ثبت شد !", "• New rate saved !"))

    convo.ask(uid, _got)


# ----------------------------------------------------------------------
# 📑 دریافت فاکتور - invoice
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📑 دریافت فاکتور$"))
async def invoice(client, m: Message):
    uid = m.from_user.id
    x = database.query("SELECT * FROM money1")
    botmusic = x[1][1] if len(x) > 1 else 0
    botvideo = x[1][2] if len(x) > 1 else 0
    froshmusic = x[0][1] if x else 0
    froshvideo = x[0][2] if x else 0
    paye = database.query("SELECT nerkh FROM paye WHERE kos=1")
    paye = paye[0][0] if paye else 0

    mus_count = len([*database.moz(0), *database.moz(1)])
    vid_count = len([*database.kir(0), *database.kir(1)])

    fa = (
        f"**◄ وضعیت فاکتور شما به شرح زیر است :**\n\n"
        f"◂ تعداد کل گروه ها موزیک : {mus_count}\n"
        f"◂ تعداد کل گروه ها ویدیو : {vid_count}\n\n"
        f"╕ نرخ هر گروه موزیک {botmusic} تومان است.\n"
        f"╛ نرخ هر گروه ویدیو {botvideo} تومان است.\n\n"
        f"─━━━━━━━━━━━━━━━━━━━─\n\n"
        f"▐ نرخ فروش موزیک : {froshmusic}\n\n"
        f"▐ نرخ فروش ویدیو : {froshvideo}\n\n"
        f"─━━━━━━━━━━━━━━━━━━━─\n\n"
        f"▐ مبلغ کل دریافتی شما از موزیک : {froshmusic * mus_count}\n\n"
        f"▐ مبلغ کل دریافتی شما از ویدیو : {froshvideo * vid_count}\n\n"
        f"─━━━━━━━━━━━━━━━━━━━─\n\n"
        f"**▐ هزینه پایه : {paye} تومان.**\n\n"
        f"**▐ کل هزینه قابل پرداخت : {(botmusic * mus_count) + (botvideo * vid_count) + paye} تومان.**\n\n"
        f"• این فاکتور به صورت درخواستی صرفاً جهت اطلاع از هزینه ها ارسال شده است و قابل پرداخت نیست."
    )
    en = (
        f"**◄ Your invoice :**\n\n"
        f"◂ Total music groups : {mus_count}\n"
        f"◂ Total video groups : {vid_count}\n\n"
        f"╕ Music group price : {botmusic} toman\n"
        f"╛ Video group price : {botvideo} toman\n\n"
        f"─━━━━━━━━━━━━━━━━━━━─\n\n"
        f"▐ Music sale price : {froshmusic}\n\n"
        f"▐ Video sale price : {froshvideo}\n\n"
        f"─━━━━━━━━━━━━━━━━━━━─\n\n"
        f"▐ Your total income from music : {froshmusic * mus_count}\n\n"
        f"▐ Your total income from video : {froshvideo * vid_count}\n\n"
        f"─━━━━━━━━━━━━━━━━━━━─\n\n"
        f"**▐ Base cost : {paye} toman.**\n\n"
        f"**▐ Total payable : {(botmusic * mus_count) + (botvideo * vid_count) + paye} toman.**\n\n"
        f"• This invoice is informational only and cannot be paid."
    )
    await m.reply(i18n.t(uid, fa, en))


# ----------------------------------------------------------------------
# تنظیم اعتبار / اپدیت اعتبار / 📆 میزان اعتبار (bot credit)
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^(تنظیم اعتبار)"))
async def set_credit(client, m: Message):
    uid = m.from_user.id
    text = m.text.replace("تنظیم اعتبار", "").strip()
    try:
        days = int(text)
    except ValueError:
        return await m.reply(i18n.t(uid, "لطفا شارژ ربات را به صورت عدد و بر حسب روز وارد کنید !", "Please enter the bot credit in days (number) !"))
    if database.credit_status() is not None:
        return await m.reply(i18n.t(uid, "• لطفا از دستور اپدیت اعتبار استفاده کنید !", "• Please use the update-credit command !"))
    now = time.time()
    database.execute("INSERT INTO etebar(kos,start,end,status) VALUES(?,?,?,?)", (1, now, now + float(days * 86400), 0))
    await m.reply(i18n.t(uid, "• ربات به مدت خواسته شده شارژ شد !", "• Bot credit set !"))


@app.on_message(filters.private & filters.user(OWNER) & filters.regex(r"^(اپدیت اعتبار)"))
async def update_credit(client, m: Message):
    uid = m.from_user.id
    text = m.text.replace("اپدیت اعتبار", "").strip()
    try:
        days = int(text)
    except ValueError:
        return await m.reply(i18n.t(uid, "• لطفا شارژ ربات را به صورت عدد و بر حسب روز وارد کنید !", "• Please enter the bot credit in days (number) !"))
    if database.credit_status() is None:
        return await m.reply(i18n.t(uid, "• لطفا از دستور تنظیم اعتبار استفاده کنید !", "• Please use the set-credit command !"))
    database.execute("UPDATE etebar SET start=?, end=?, status=0", (time.time(), time.time() + float(days * 86400)))
    await m.reply(i18n.t(uid, "• ربات به مدت خواسته شده شارژ شد !", "• Bot credit updated !"))


@app.on_message(filters.private & filters.user([OWNER, SUDO]) & filters.regex(r"^📆 میزان اعتبار$"))
async def credit_check(client, m: Message):
    uid = m.from_user.id
    row = database.credit_status()
    if row is None:
        return await m.reply(i18n.t(uid, "• لطفا ابتدا اعتباری برای ربات تنظیم کنید و سپس تلاش کنید !", "• Please set a credit for the bot first !"))
    start, end, status = row[1], row[2], row[3]
    nowh = round((end - time.time()) / 86400, 0)
    nowm = round((end - time.time()) / 60 / 60, 0)
    if status in (0, 1, 2):
        await m.reply(i18n.t(uid, f"• ربات شما به مدت {nowh} روز اعتبار دارد !", f"• Your bot has {nowh} days of credit !"))
    elif status == 3:
        await m.reply(i18n.t(uid, f"• ربات شما به مدت {nowm} ساعت اعتبار دارد !", f"• Your bot has {nowm} hours of credit !"))
    else:
        await m.reply(i18n.t(uid, "• ربات فاقد اعتبار میباشد !", "• The bot has no credit !"))
