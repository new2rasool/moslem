"""
Background tasks (replacement for the original broken aiocron jobs).

- check music group credits (48h reminder / expiry / auto-leave)
- check video group credits
- check the bot's own credit (5 / 3 / 1 day reminders + final invoice)
- refresh group names & invite links stored in the database
"""
import asyncio
import logging
import time

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
import database
import utils
from clients import app, ubot, call_py, helper_session_exists

logger = logging.getLogger("musicrasool.tasks")
cfg = config.get_config()
OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID


async def _leave_group(chat_id):
    try:
        await app.leave_chat(chat_id)
    except Exception:
        pass
    if helper_session_exists():
        try:
            await ubot.leave_chat(chat_id)
        except Exception:
            pass


def _charge_button():
    info = database.info() or {}
    payamresan = info.get("payamresan") or "dbgchjnebdh"
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("☜ شارژ گروه توسط مدیر ربات ☞", url=f"https://t.me/{payamresan}")]]
    )


async def check_music_expiry():
    """Every ~10 minutes - charge table."""
    while True:
        try:
            # status 0 -> less than 48h left -> status 1 + notify
            for i in database.query("SELECT * FROM charge WHERE status=0"):
                now = time.time()
                end = i[4]
                h48 = end - 172800.1
                if now > h48:
                    chat_id = int(i[0])
                    try:
                        req = await app.get_chat(chat_id)
                        req2 = await app.get_chat(int(i[1]))
                        database.execute("UPDATE charge SET status=1 WHERE idgp=?", (chat_id,))
                        row = database.query("SELECT * FROM charge WHERE idgp=?", (chat_id,))
                        saat = 0
                        if row:
                            saat = int(int(row[0][4] - time.time()) / 60 / 60)
                        await app.send_message(
                            SUDO,
                            f"◄ تاریخ تمدید این گروه فرا رسید !\n\n"
                            f"┈┅━─━| **اطلاعات گروه** |━─━┅┈\n"
                            f"◂ نام گروه : **{req.title}**\n"
                            f"◂ شناسه گروه : `{req.id}`\n"
                            f"◂ اعتبار گروه : کمتر از {saat} ساعت\n"
                            f"◂ لینک گروه : [برای ورود به گروه کلیک کنید.]({req.invite_link})\n\n"
                            f"┈┅━─━| **اطلاعات مالک گروه** |━─━┅┈\n"
                            f"◂ نام مالک : **{req2.first_name}**\n"
                            f"◂ شناسه مالک : `{req2.id}`\n"
                            f"◂ یوزر نیم مالک : [کلیک کنید.](tg://openmessage?user_id={req2.id})",
                            disable_web_page_preview=True,
                        )
                        xs = await app.send_message(
                            chat_id,
                            f"⚠️ اعتبار گروه شما کمتر از {saat} ساعت میباشد !\n\n"
                            f"◂ لطفاً جهت جلوگیری از خارج شدن ربات ، هرچه سریعتر به پشتیبانی ربات مراجعه نمایید.",
                            reply_markup=_charge_button(),
                        )
                        try:
                            await xs.pin()
                        except Exception:
                            pass
                        try:
                            await app.send_message(
                                int(i[1]),
                                f"**⚠️ مدیر گرامی اعتبار گروه شما رو به اتمام است !**\n\n"
                                f"◂ لطفاً جهت جلوگیری از خارج شدن ربات ، هرچه سریعتر به پشتیبانی ربات مراجعه نمایید.\n"
                                f"**\n🪧 نام گروه : {req.title}\n⏳ زمان باقی مانده : {saat} ساعت**",
                                reply_markup=_charge_button(),
                            )
                        except Exception:
                            pass
                    except Exception as exc:
                        logger.warning("music expiry notify failed: %s", exc)
                    await asyncio.sleep(1)
                await asyncio.sleep(0.4)

            # status 1 -> expired -> status 2 + notify + auto leave
            for i in database.query("SELECT * FROM charge WHERE status=1"):
                now = time.time()
                end = i[4]
                if now > end:
                    chat_id = int(i[0])
                    try:
                        req = await app.get_chat(chat_id)
                        req2 = await app.get_chat(int(i[1]))
                        database.execute("UPDATE charge SET status=2 WHERE idgp=?", (chat_id,))
                        await app.send_message(
                            SUDO,
                            f"**◄ تاریخ تمدید این گروه فرا رسید !**\n\n"
                            f"┈┅┅━━| **اطلاعات گروه** |━━┅┅┈\n"
                            f"◂ نام گروه : `{req.title}`\n"
                            f"◂ شناسه گروه : `{req.id}`\n"
                            f"◂ لینک گروه : [برای ورود به گروه کلیک کنید.]({req.invite_link})\n"
                            f"┈┅┅━━| **صاحب گروه** |━━┅┅┈\n"
                            f"◂ نام : `{req2.first_name}`\n"
                            f"◂ شناسه : `{req2.id}`\n"
                            f"◂ یوزرنیم : @{req2.username}",
                            disable_web_page_preview=True,
                        )
                        try:
                            await app.send_message(int(i[1]), f"**◂ اعتبار گروه شما با نام {req.title} به پایان رسید !**", reply_markup=_charge_button())
                        except Exception:
                            pass
                        xs = await app.send_message(chat_id, "**◂ اعتبار این گروه به پایان رسیده است، جهت شارژ مجدد به پشتیبانی مراجعه کنید !**", reply_markup=_charge_button())
                        try:
                            await xs.pin()
                        except Exception:
                            pass
                        await asyncio.sleep(1)
                        left_rows = database.query("SELECT status FROM autoleft")
                        if left_rows and left_rows[0][0] == 1:
                            database.execute("DELETE FROM musicadmin WHERE idgp=?", (chat_id,))
                            database.execute("DELETE FROM gp WHERE idgp=? AND status=0", (chat_id,))
                            database.execute("DELETE FROM charge WHERE idgp=?", (chat_id,))
                            if chat_id not in [*database.kir(0), *database.kir(1)]:
                                await _leave_group(chat_id)
                    except Exception as exc:
                        logger.warning("music expiry finalize failed: %s", exc)
                await asyncio.sleep(0.4)
        except Exception as exc:
            logger.warning("check_music_expiry loop error: %s", exc)
        await asyncio.sleep(600)


async def check_video_expiry():
    """Every ~18 minutes - charge2 table."""
    while True:
        try:
            for i in database.query("SELECT * FROM charge2 WHERE status=0"):
                now = time.time()
                end = i[4]
                h48 = end - 172800.1
                if now > h48:
                    chat_id = int(i[0])
                    try:
                        req = await app.get_chat(chat_id)
                        req2 = await app.get_chat(int(i[1]))
                        database.execute("UPDATE charge2 SET status=1 WHERE idgp=?", (chat_id,))
                        row = database.query("SELECT * FROM charge2 WHERE idgp=?", (chat_id,))
                        saat = 0
                        if row:
                            saat = int(int(row[0][4] - time.time()) / 60 / 60)
                        await app.send_message(
                            SUDO,
                            f"◄ تاریخ تمدید این گروه برای ویدیو فرا رسید !\n\n"
                            f"┈┅━─━| **اطلاعات گروه** |━─━┅┈\n"
                            f"◂ نام گروه : **{req.title}**\n"
                            f"◂ شناسه گروه : `{req.id}`\n"
                            f"◂ اعتبار گروه : کمتر از {saat} ساعت\n"
                            f"◂ لینک گروه : [برای ورود به گروه کلیک کنید.]({req.invite_link})\n\n"
                            f"┈┅━─━| **اطلاعات مالک گروه** |━─━┅┈\n"
                            f"◂ نام مالک : **{req2.first_name}**\n"
                            f"◂ شناسه مالک : `{req2.id}`\n"
                            f"◂ یوزر نیم مالک : [کلیک کنید.](tg://openmessage?user_id={req2.id})",
                            disable_web_page_preview=True,
                        )
                        xs = await app.send_message(
                            chat_id,
                            f"⚠️ اعتبار گروه شما کمتر از {saat} ساعت میباشد !\n\n"
                            f"◂ لطفاً جهت جلوگیری از خارج شدن ربات ، هرچه سریعتر به پشتیبانی ربات مراجعه نمایید.\n#Video",
                            reply_markup=_charge_button(),
                        )
                        try:
                            await xs.pin()
                        except Exception:
                            pass
                        try:
                            await app.send_message(
                                int(i[1]),
                                f"**⚠️ مدیر گرامی اعتبار گروه ویدیو شما رو به اتمام است !**\n\n"
                                f"◂ لطفاً جهت جلوگیری از خارج شدن ربات ، هرچه سریعتر به پشتیبانی ربات مراجعه نمایید.\n"
                                f"**\n🪧 نام گروه : {req.title}\n⏳ زمان باقی مانده : {saat} ساعت**",
                                reply_markup=_charge_button(),
                            )
                        except Exception:
                            pass
                    except Exception as exc:
                        logger.warning("video expiry notify failed: %s", exc)
                await asyncio.sleep(0.5)

            for i in database.query("SELECT * FROM charge2 WHERE status=1"):
                now = time.time()
                end = i[4]
                if now > end:
                    chat_id = int(i[0])
                    try:
                        req = await app.get_chat(chat_id)
                        req2 = await app.get_chat(int(i[1]))
                        database.execute("UPDATE charge2 SET status=2 WHERE idgp=?", (chat_id,))
                        await app.send_message(
                            SUDO,
                            f"**◄ تاریخ تمدید این گروه ویدیو فرا رسید !**\n\n"
                            f"┈┅┅━━| **اطلاعات گروه** |━━┅┅┈\n"
                            f"◂ نام گروه : `{req.title}`\n"
                            f"◂ شناسه گروه : `{req.id}`\n"
                            f"◂ لینک گروه : [برای ورود به گروه کلیک کنید.]({req.invite_link})\n"
                            f"┈┅┅━━| **صاحب گروه** |━━┅┅┈\n"
                            f"◂ نام : `{req2.first_name}`\n"
                            f"◂ شناسه : `{req2.id}`\n"
                            f"◂ یوزرنیم : @{req2.username}",
                            disable_web_page_preview=True,
                        )
                        try:
                            await app.send_message(int(i[1]), f"**◂ اعتبار گروه شما با نام {req.title} به پایان رسید !**", reply_markup=_charge_button())
                        except Exception:
                            pass
                        xs = await app.send_message(chat_id, "**◂ اعتبار ویدیو این گروه به پایان رسیده است، جهت شارژ مجدد به پشتیبانی مراجعه کنید !**", reply_markup=_charge_button())
                        try:
                            await xs.pin()
                        except Exception:
                            pass
                        left_rows = database.query("SELECT status FROM autoleft")
                        if left_rows and left_rows[0][0] == 1:
                            database.execute("DELETE FROM videoadmins WHERE idgp=?", (chat_id,))
                            database.execute("DELETE FROM gp WHERE idgp=? AND status=1", (chat_id,))
                            database.execute("DELETE FROM charge2 WHERE idgp=?", (chat_id,))
                            if chat_id not in [*database.moz(0), *database.moz(1)]:
                                await _leave_group(chat_id)
                    except Exception as exc:
                        logger.warning("video expiry finalize failed: %s", exc)
                await asyncio.sleep(0.4)
        except Exception as exc:
            logger.warning("check_video_expiry loop error: %s", exc)
        await asyncio.sleep(1080)


async def check_bot_credit():
    """Every ~10 minutes - the bot's own credit (etebar)."""
    while True:
        try:
            row = database.credit_status()
            if row is None:
                await asyncio.sleep(600)
                continue
            start, end, status = row[1], row[2], row[3]
            d5 = end - 432000.0
            d3 = end - 259200.0
            d1 = end - 86400.0
            if time.time() >= d5 and status == 0:
                a = await app.send_message(SUDO, "• تنها پنج روز به اتمام اشتراک ربات شما باقی مانده است ، بعد از اتمام اشتراک ربات به صورت خودکار افلاین خواهد شد !")
                try:
                    await a.pin(both_sides=True)
                except Exception:
                    pass
                b = await app.send_message(OWNER, "• برنامه نویس عزیز تنها 5 روز به اتمام اشتراک این ربات باقی مانده است !")
                try:
                    await b.pin(both_sides=True)
                except Exception:
                    pass
                database.execute("UPDATE etebar SET status=1")
            elif time.time() >= d3 and status == 1:
                a = await app.send_message(SUDO, "• تنها سه روز به اتمام اعتبار ربات شما باقی مانده است ، بعد از اتمام اشتراک ربات به صورت خودکار افلاین خواهد شد !")
                try:
                    await a.pin(both_sides=True)
                except Exception:
                    pass
                b = await app.send_message(OWNER, "• برنامه نویس عزیز تنها سه روز به اتمام اشتراک این ربات باقی مانده است !")
                try:
                    await b.pin(both_sides=True)
                except Exception:
                    pass
                database.execute("UPDATE etebar SET status=2")
            elif time.time() >= d1 and status == 2:
                a = await app.send_message(SUDO, "• تنها یک روز به اتمام اعتبار ربات شما باقی مانده است ، بعد از اتمام اشتراک ربات به صورت خودکار افلاین خواهد شد !")
                try:
                    await a.pin(both_sides=True)
                except Exception:
                    pass
                b = await app.send_message(OWNER, "• برنامه نویس عزیز تنها یک روز به اتمام اشتراک این ربات باقی مانده است !")
                try:
                    await b.pin(both_sides=True)
                except Exception:
                    pass
                database.execute("UPDATE etebar SET status=3")
            elif time.time() >= end and status == 3:
                a = await app.send_message(SUDO, "اعتبار ربات شما به اتمام رسید لطفا قبل از حذف دیتا جهت تسویه اقدام کنید !")
                try:
                    await a.pin(both_sides=True)
                except Exception:
                    pass
                b = await app.send_message(OWNER, "• برنامه نویس عزیز اعتبار این ربات به پایان رسیده میتوانید از بخش پیام به سودو درخواست تسویه ربات بدهید !")
                try:
                    await b.pin(both_sides=True)
                except Exception:
                    pass
                database.execute("UPDATE etebar SET status=4")
        except Exception as exc:
            logger.warning("check_bot_credit error: %s", exc)
        await asyncio.sleep(600)


async def refresh_group_info():
    """Every ~20 minutes - update stored group names/links."""
    while True:
        try:
            for i in database.query("SELECT * FROM charge WHERE status IN (0,1,2)"):
                try:
                    client = app if not helper_session_exists() else ubot
                    req = await client.get_chat(int(i[0]))
                    database.execute("UPDATE charge SET name=?, link=? WHERE idgp=?", (req.title, req.invite_link, int(i[0])))
                except Exception:
                    pass
                await asyncio.sleep(0.5)
            for i in database.query("SELECT * FROM charge2 WHERE status IN (0,1,2)"):
                try:
                    client = app if not helper_session_exists() else ubot
                    req = await client.get_chat(int(i[0]))
                    database.execute("UPDATE charge2 SET name=?, link=? WHERE idgp=?", (req.title, req.invite_link, int(i[0])))
                except Exception:
                    pass
                await asyncio.sleep(0.5)
        except Exception as exc:
            logger.warning("refresh_group_info error: %s", exc)
        await asyncio.sleep(1200)


async def _binding_active(chat_id):
    """True if the native binding reports an active (non-idling) call.

    Returns None when the probe itself fails - callers MUST treat None as
    "do nothing" (non-destructive) instead of assuming the call is gone.
    """
    try:
        from clients import call_py

        calls = call_py._binding.calls()  # sync dict {chat_id: StreamStatus}
        status = calls.get(chat_id)
        if status is None:
            return False
        name = getattr(status, "name", "")
        if not name:
            # unknown status representation -> be conservative
            return True
        return name.upper() != "IDLING"
    except Exception:  # noqa: BLE001
        return None


async def _watch_once():
    """One auto-reconnect iteration (testable)."""
    if not utils.STREAMS:
        return
    now = time.time()
    for chat_id, info in list(utils.STREAMS.items()):
        # Give freshly started streams time to settle so we never
        # reconnect during the join/start phase.
        if now - info.get("started_at", now) < 30:
            continue
        # Playlists are driven by their own runner.
        if chat_id in utils.PLAYLIS:
            continue
        state = await _binding_active(chat_id)
        if state is True:
            # stream is alive - reset any failure counter
            info["fails"] = 0
            continue
        if state is None:
            # can't probe - never take destructive action on uncertainty
            continue

        # ------------------------------------------------------------
        # Binding reports the call is gone (idle / absent) -> reconnect
        # ------------------------------------------------------------
        info["fails"] = info.get("fails", 0) + 1
        if info["fails"] > 3:
            logger.info("Giving up auto-reconnect for %s", chat_id)
            utils.clear_streaming(chat_id)
            try:
                await call_py.leave_group_call(chat_id)
            except Exception:  # noqa: BLE001
                pass
            continue
        info["ignore_until"] = time.time() + 6
        try:
            await utils.rejoin_stream(chat_id, info)
            info["fails"] = 0
            logger.info("Reconnected stream in chat %s", chat_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Reconnect failed for %s: %s", chat_id, exc)


async def watch_streams():
    """Auto-reconnect: if an intentionally-playing stream (STREAMS) drops
    unexpectedly (voice chat closed, network loss, kicked), re-join it.
    Only streams that are still marked in STREAMS are reconnected, so
    intentional stops never trigger a reconnect. Gives up after 3 failed
    reconnect attempts to avoid infinite retry loops, and NEVER acts
    destructively when the call state cannot be probed."""
    while True:
        try:
            await _watch_once()
        except Exception as exc:  # noqa: BLE001
            logger.warning("watch_streams error: %s", exc)
        await asyncio.sleep(15)


async def run_all_tasks():
    await asyncio.gather(
        check_music_expiry(),
        check_video_expiry(),
        check_bot_credit(),
        refresh_group_info(),
        watch_streams(),
    )
