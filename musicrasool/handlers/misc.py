"""
Misc handlers: help panel, ping, bot status, reply media setting,
easter eggs (card / man), and new-chat-member auto promote / ban.
"""
import asyncio
import os
import random
import time

from pyrogram import enums, filters
from pyrogram.types import ChatPrivileges, Message

import config
import database
import i18n
import utils
from clients import app

cfg = config.get_config()
OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID


# ----------------------------------------------------------------------
# راهنما / help
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^([Hh][Ee][Ll][Pp])$") | filters.regex(r"^(راهنما)$")))
async def help_cmd(client, m: Message):
    uid = m.from_user.id
    access = [*database.idmusic(m.chat.id), *database.allmusic(), *database.idvideo(m.chat.id),
              *database.allvideo(), *database.creators(m.chat.id), *database.idsudos(),
              *database.idowner(), SUDO, OWNER]
    if uid in access:
        await m.reply(
            i18n.t(uid, "• یکی از گزینه های زیر را انتخاب نمایید : \n┈┅┅━┃صفحه اصلی┃━┅┅┈", "• Choose one of the options below : \n┈┅┅━┃Home┃━┅┅┈"),
            reply_markup=utils.help_keyboard(uid),
        )


# ----------------------------------------------------------------------
# پینگ / ping
# ----------------------------------------------------------------------
def _update_latency(m) -> str:
    """Seconds between Telegram timestamping the message and us handling it."""
    date = getattr(m, "date", None)
    if date is None:
        return "-"
    try:
        return f"{max(0.0, time.time() - date.timestamp()):.3f}"
    except Exception:
        return "-"


async def _ping_card(m, uid, title_fa, title_en, recv, send=None):
    """The original progressive 'ping' card, but with measured numbers.

    Sends exactly ONE message and edits it, like the original. When `send` is
    None the send latency is measured from this card's own first reply.
    """
    head_fa = f"**⋆ {title_fa} !**"
    head_en = f"**⋆ {title_en} !**"
    lines_fa = f"{head_fa}\n◍ زمان های سپری شده **:**"
    lines_en = f"{head_en}\n◍ Elapsed times **:**"
    started = time.monotonic()
    am = await m.reply(i18n.t(uid, head_fa, head_en))
    if send is None:
        send = f"{time.monotonic() - started:.3f}"
    await asyncio.sleep(0.2)
    await am.edit(i18n.t(uid, lines_fa, lines_en))
    await asyncio.sleep(0.2)
    await am.edit(i18n.t(uid, f"{lines_fa}\n↓ دریافت ·۰• {recv} ثانیه",
                         f"{lines_en}\n↓ Receive ·۰• {recv}s"))
    await asyncio.sleep(0.2)
    await am.edit(i18n.t(uid, f"{lines_fa}\n↓ دریافت ·۰• {recv} ثانیه\n↑ ارسال ·۰•  {send} ثانیه",
                         f"{lines_en}\n↓ Receive ·۰• {recv}s\n↑ Send ·۰•  {send}s"))


@app.on_message(filters.group & (filters.regex(r"^(پینگ)$") | filters.regex(r"^([Pp][Ii][Nn][Gg])$")))
async def ping_cmd(client, m: Message):
    uid = m.from_user.id
    recv = _update_latency(m)
    # measured, not random: both numbers used to come from random.choice(),
    # so the card reported invented latencies as if they were real.
    await _ping_card(m, uid, "ربات هم اکنون آنلاین میباشد", "The bot is online now", recv)
    # `helper_ping` below matches the very same filters and lives in the same
    # handler group. Without this the dispatcher stops after the first match
    # and the helper ping could never be reached.
    m.continue_propagation()


@app.on_message(filters.group & filters.user([SUDO, OWNER]) & (filters.regex(r"^(پینگ)$") | filters.regex(r"^([Pp][Ii][Nn][Gg])$")))
async def helper_ping(client, m: Message):
    uid = m.from_user.id
    from clients import ubot, helper_ready
    if not helper_ready():
        return
    recv = _update_latency(m)
    # a real MTProto round-trip through the helper session
    started = time.monotonic()
    try:
        await ubot.get_me()
    except Exception as exc:
        await m.reply(i18n.t(uid, f"• هلپر پاسخ نداد : `{utils.brief_error(exc)}`",
                             f"• The helper did not respond : `{utils.brief_error(exc)}`"))
        return
    send = f"{time.monotonic() - started:.3f}"
    await _ping_card(m, uid, "هلپر هم اکنون آنلاین میباشد", "The helper is online now", recv, send)


# ----------------------------------------------------------------------
# ربات / bot / robot
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(ربات)$") | filters.regex(r"^([Bb][Oo][Tt])$") | filters.regex(r"^([Rr][Oo][Bb][Oo][Tt])$")))
async def bot_status(client, m: Message):
    uid = m.from_user.id
    try:
        async for member in client.get_chat_members(m.chat.id, filter=enums.ChatMembersFilter.ADMINISTRATORS):
            if member.user and member.user.id == uid:
                answers = [
                    "◂ ربات آنلاین است 🙃", "◂ جونم اَمر بفرما 😢", "◂ کاری داشتی 🤔",
                    "◂ جانم عشقم 😍", "◂ جـانم عزیزم 😄", "◂ پر سرعت مثل همیشه 😎",
                    "◂ ربات درحال حاضر آنلاین میباشد !", "◂ جونم مدیر عزیز 😉",
                    "◂ در انتظار دستورات شما 😁", "◂ جانم 😅", "◂ خوشگل گروه خودتی 😉",
                    "◂ بله عزیزم 🙂",
                ]
                await m.reply(f"**{random.choice(answers)}**")
                return
    except Exception:
        pass


# ----------------------------------------------------------------------
# تنظیم مدیای پاسخ (set the now-playing card media: photo / gif)
# ----------------------------------------------------------------------
@app.on_message(filters.regex(r"^(تنظیم مدیای پاسخ)$") & filters.reply & filters.user([OWNER, SUDO]))
async def set_reply_media(client, m: Message):
    uid = m.from_user.id
    photo = os.path.join(cfg.ASSETS_DIR, "mersad.jpg")
    video = os.path.join(cfg.ASSETS_DIR, "mersad.mp4")
    try:
        if m.reply_to_message.photo:
            if os.path.exists(photo):
                os.remove(photo)
            if os.path.exists(video):
                os.remove(video)
            await m.reply_to_message.download(file_name=photo)
            await m.reply(i18n.t(uid, "• تصویر به عنوان مدیای پاسخ قرار گرفت !", "• The photo was set as the reply media !"))
        elif m.reply_to_message.media:
            # any non-photo media (video / gif / animation) -> mersad.mp4
            if os.path.exists(photo):
                os.remove(photo)
            if os.path.exists(video):
                os.remove(video)
            await m.reply_to_message.download(file_name=video)
            await m.reply(i18n.t(uid, "• ویدیو به عنوان مدیای پاسخ قرار گرفت !", "• The video was set as the reply media !"))
        else:
            await m.reply(i18n.t(uid, "• لطفا به یک تصویر یا ویدیو ریپلای کنید !", "• Please reply to a photo or a video !"))
    except Exception as exc:
        print(f"set reply media failed: {exc!r}")
        await m.reply(i18n.t(uid, f"• خطا : `{utils.brief_error(exc)}`", f"• Error : `{utils.brief_error(exc)}`"))


# ----------------------------------------------------------------------
# Easter eggs (owner)
# ----------------------------------------------------------------------
@app.on_message(filters.user(OWNER) & (filters.regex(r"^(کارت)$") | filters.regex(r"^([Cc][Aa][Rr][Dd])$")))
async def card_egg(client, m: Message):
    await m.reply("👉 `6037998240935196` 👈\n**💳 #بانک_ملی\n\nبه نام : محمدامین داوری 🔖\n\n❌ اسکرین از فیش الزامی میباشد 📸**")


@app.on_message(filters.user(OWNER) & (filters.regex(r"^(من کیم)$") | filters.regex(r"^([Mm][Aa][Nn])$")))
async def man_egg(client, m: Message):
    await m.reply("شما مرصاد **برنامه نویس** ربات هستی")


@app.on_message(filters.user(OWNER) & filters.regex(r"^(bank)$"))
async def bank_egg(client, m: Message):
    await m.reply("**My Sepah Bank :**\n➛ `5892101325981906`")


# ----------------------------------------------------------------------
# New chat members: global ban check + auto-promote sudos
# ----------------------------------------------------------------------
@app.on_message(filters.new_chat_members & filters.group)
async def new_member_handler(client, m: Message):
    for member in m.new_chat_members:
        if member.is_self:
            continue
        if database.query("SELECT ban FROM banlist WHERE ban=?", (member.id,)) != []:
            try:
                await client.ban_chat_member(m.chat.id, member.id)
            except Exception:
                pass
            continue
        if member.id in (OWNER, SUDO, *database.idsudos()):
            try:
                await app.promote_chat_member(
                    m.chat.id, member.id,
                    privileges=ChatPrivileges(
                        can_pin_messages=True,
                        can_restrict_members=True,
                        can_promote_members=True,
                        can_invite_users=True,
                        can_delete_messages=True,
                        can_manage_video_chats=True,
                    ),
                )
                title = "⋆ برنامه نویس ⋆" if member.id == OWNER else "⋆ پشتیبان ربات ⋆"
                await app.set_administrator_title(m.chat.id, member.id, title)
                if member.id != OWNER:
                    try:
                        await app.send_message(
                            SUDO,
                            f"◄ یک سودو پس از وارد شدن به گپ **{m.chat.title}** ادمین شد !\n\n"
                            f"┈┅━─━| **اطلاعات گروه** |━─━┅┈\n"
                            f"◂ نام گروه : **{m.chat.title}**\n"
                            f"◂ شناسه گروه : `{m.chat.id}`\n\n"
                            f"┈┅━─━| **اطلاعات سودو** |━─━┅┈\n"
                            f"◂ نام سودو : **{member.first_name}**\n"
                            f"◂ شناسه سودو : `{member.id}`\n"
                            f"◂ یوزر نیم سودو : @{member.username}"
                        )
                    except Exception:
                        pass
            except Exception:
                pass
