"""
Private-chat handlers: /start, /language, /login (helper account),
/restart and the owner/sudo reply-keyboard panel.
"""
import os
import sys

from pyrogram import filters
from pyrogram.types import Message, ReplyKeyboardMarkup

import config
import database
import i18n
import utils
from clients import app

cfg = config.get_config()

# ----------------------------------------------------------------------
# Owner / sudo reply-keyboard panels (EXACT original layout & order)
# ----------------------------------------------------------------------
panel_fa_owner = [
    ["📊 وضعیت"],
    ["📑 دریافت فاکتور", "📆 میزان اعتبار"],
    ["تنظیم نرخ پایه"],
    ["تنظیم نرخ ویدیو", "تنظیم نرخ موزیک"],
    ["نرخ فروش موزیک", "نرخ فروش ویدیو"],
    ["📨 ارسال همگانی", "📨 ارسال همگانی گروه ها"],
    ["▪️اجبار ورود فعال", "▫️اجبار ورود غیرفعال"],
    ["📋 لیست گروه های فعال موزیک"],
    ["📁 لیست گروه های تمدید موزیک"],
    ["📋 لیست گروه های فعال ویدیو"],
    ["📁 لیست گروه های تمدید ویدیو"],
    ["⚠️ لیست گروه های فاقد اعتبار"],
    ["❌ حذف سودو", "📌 تنظیم سودو"],
    ["❌ حذف ادمین", "📌 تنظیم ادمین"],
    ["👥 لیست سودو های ربات"],
    ["🗑 حذف گروه ویدیو", "🗑 حذف گروه موزیک"],
    ["📬 ارسال به سودو"],
    ["✏️ تنظیم استارت", "📚 تنظیم درباره ما"],
    ["📬 تنظیم پیامرسان", "📥 تنظیم پی وی"],
    ["📢 تنظیم کانال", "👥 تنظیم گروه"],
    ["تنظیم محدودیت 🔏", "✏️ تنظیم استارت هلپر"],
    ["محدودیت نصب فعال ⚠️", "محدودیت نصب غیرفعال ♻️"],
    ["▪️ خروج خودکار فعال", "▫️ خروج خودکار غیرفعال"],
]

panel_fa_sudo = [
    ["📊 وضعیت"],
    ["📑 دریافت فاکتور", "📆 میزان اعتبار"],
    ["📨 ارسال همگانی", "📨 ارسال همگانی گروه ها"],
    ["▪️اجبار ورود فعال", "▫️اجبار ورود غیرفعال"],
    ["📋 لیست گروه های فعال موزیک"],
    ["📁 لیست گروه های تمدید موزیک"],
    ["📋 لیست گروه های فعال ویدیو"],
    ["📁 لیست گروه های تمدید ویدیو"],
    ["⚠️ لیست گروه های فاقد اعتبار"],
    ["❌ حذف سودو", "📌 تنظیم سودو"],
    ["❌ حذف ادمین", "📌 تنظیم ادمین"],
    ["👥 لیست سودو های ربات"],
    ["🗑 حذف گروه ویدیو", "🗑 حذف گروه موزیک"],
    ["▪️ خروج خودکار فعال", "▫️ خروج خودکار غیرفعال"],
]

# ----------------------------------------------------------------------
# /start
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.command("start"))
async def startt(client, m: Message):
    uid = m.from_user.id if m.from_user else m.chat.id
    database.add_user(uid)

    info = database.info() or {}
    ch_rows = database.channel()
    channel_link = ch_rows[0][2] if ch_rows else "https://t.me/fnvhfdmnfhjkc"

    start_text = info.get("start") or "START"
    if "MENTION" in start_text:
        start_text = start_text.replace("MENTION", m.from_user.mention(m.from_user.first_name))
    if "BOLD" in start_text:
        start_text = start_text.replace("BOLD", "**")
    if "USERID" in start_text:
        start_text = str(start_text).replace("USERID", str(m.from_user.id))

    markup = utils.start_keyboard(uid, info, channel_link)
    await m.reply(start_text, reply_markup=markup)

    if uid == cfg.OWNER_ID:
        await client.send_message(
            uid,
            i18n.t(uid, "**◆ به پنل برنامه نویس خوش آمدید ♡**", "**◆ Welcome to the Developer Panel ♡**"),
            reply_to_message_id=m.id,
            reply_markup=ReplyKeyboardMarkup(
                panel_fa_owner, resize_keyboard=True, one_time_keyboard=True
            ),
        )
    elif uid == cfg.SUDO_ID or uid in database.idsudos() or uid in database.idowner():
        await client.send_message(
            uid,
            i18n.t(uid, "**◆ به پنل ادمین خوش آمدید ♡**", "**◆ Welcome to the Admin Panel ♡**"),
            reply_to_message_id=m.id,
            reply_markup=ReplyKeyboardMarkup(
                panel_fa_sudo, resize_keyboard=True, one_time_keyboard=True
            ),
        )

    # reminder about the helper account
    from clients import helper_session_exists
    if uid in (cfg.OWNER_ID, cfg.SUDO_ID) and not helper_session_exists():
        await client.send_message(
            uid,
            i18n.t(
                uid,
                "⚠️ **حساب هلپر هنوز وارد نشده است!**\n"
                "برای پخش موزیک/ویدیو در ویس کال، لطفا دستور `/login` را ارسال کنید و "
                "مراحل ورود (شماره تلفن و کد ورود) را انجام دهید.",
                "⚠️ **The Helper account is not logged in yet!**\n"
                "To stream music/video in voice chats please send `/login` and "
                "follow the steps (phone number and login code).",
            ),
        )


# ----------------------------------------------------------------------
# /language - switch the user interface language
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.command("language"))
async def language_cmd(client, m: Message):
    uid = m.from_user.id if m.from_user else m.chat.id
    await m.reply(
        i18n.t(uid, "• لطفا زبان مورد نظر خود را انتخاب کنید :", "• Please choose your language :"),
        reply_markup=i18n.language_keyboard(uid),
    )


# ----------------------------------------------------------------------
# /restart - gracefully restart the bot (used after helper login)
# ----------------------------------------------------------------------
@app.on_message(filters.private & filters.command("restart"))
async def restart_cmd(client, m: Message):
    uid = m.from_user.id if m.from_user else m.chat.id
    if uid not in utils.sudo_access():
        return
    await m.reply(i18n.t(uid, "**⌯** ربات در حال ری استارت میباشد ...", "**⌯** Restarting the bot ..."))
    try:
        from clients import call_py
        await call_py.stop()
    except Exception:
        pass
    try:
        await client.stop()
    except Exception:
        pass
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.execv(sys.executable, [sys.executable, os.path.join(base, "run.py")])


# ----------------------------------------------------------------------
# /login - helper account login wizard (owner only)
# ----------------------------------------------------------------------
# conversation states: uid -> {"step": "phone"|"code"|"password", "phone": ...}
LOGIN_STATE = {}


@app.on_message(filters.private & filters.command("login"))
async def login_cmd(client, m: Message):
    uid = m.from_user.id if m.from_user else m.chat.id
    if uid not in (cfg.OWNER_ID, cfg.SUDO_ID):
        return

    from clients import helper_session_exists
    if helper_session_exists():
        await m.reply(
            i18n.t(
                uid,
                "✅ **حساب هلپر از قبل وارد شده است!**\nبرای ورود مجدد ابتدا فایل "
                "`sessions/helper.session` را حذف کرده و دوباره تلاش کنید.",
                "✅ **The Helper account is already logged in!**\nTo re-login delete "
                "`sessions/helper.session` and try again.",
            )
        )
        return

    LOGIN_STATE[uid] = {"step": "phone"}
    await m.reply(
        i18n.t(
            uid,
            "📲 **مرحله ۱ از ۳**\n"
            "شماره تلفن حساب هلپر را به صورت بین‌المللی وارد کنید :\n"
            "مثال : `+989123456789`\n\n"
            "_(برای انصراف /cancel را ارسال کنید)_",
            "📲 **Step 1 of 3**\n"
            "Enter the Helper account phone number in international format :\n"
            "Example : `+989123456789`\n\n"
            "_(send /cancel to abort)_",
        )
    )


@app.on_message(filters.private & filters.command("cancel"))
async def cancel_cmd(client, m: Message):
    uid = m.from_user.id if m.from_user else m.chat.id
    if uid in LOGIN_STATE:
        LOGIN_STATE.pop(uid, None)
        await m.reply(i18n.t(uid, "• فرآیند ورود لغو شد !", "• Login process cancelled !"))
