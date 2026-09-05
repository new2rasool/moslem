"""
Helper account login flow (through the bot).

The bot walks the owner through:
  1. phone number  -> cli.send_code()
  2. login code    -> cli.sign_in()
  3. (optional) 2FA password -> cli.check_password()

A throwaway Pyrogram client is used so the running bot is not
disturbed; the session file is written to sessions/helper.session
and the bot must be restarted (/restart) to use it.
"""
import inspect
import logging

from pyrogram import Client, ContinuePropagation, filters
from pyrogram.errors import (
    BadRequest,
    PhoneCodeExpired,
    PhoneCodeInvalid,
    SessionPasswordNeeded,
    PhoneNumberInvalid,
)
from pyrogram.types import Message

import config
import i18n
from clients import app
from handlers.private import LOGIN_STATE

logger = logging.getLogger("musicrasool.auth")
cfg = config.get_config()


async def _do_sign_in(cli, phone_number, phone_code_hash, phone_code):
    """Call cli.sign_in() safely on ANY Pyrogram version/fork.

    The library's signature changed across versions (Pyrogram 1.x and
    2.x differ, and pyromod-style forks may rename/order parameters).
    Mixing positional + keyword arguments for the same parameter raises:

        TypeError: sign_in() got multiple values for argument '...'

    To make that impossible we ALWAYS pass keyword arguments built from
    the real parameter names of the installed client's sign_in method.
    """
    kwargs = {}
    try:
        sig = inspect.signature(cli.sign_in)
        names = [
            p.name
            for p in sig.parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
        ]
        # map our logical values onto the library's real parameter names
        for logical, value in (
            ("phone_number", phone_number),
            ("phone_code_hash", phone_code_hash),
            ("phone_code", phone_code),
        ):
            for name in names:
                if logical in name and name not in kwargs:
                    kwargs[name] = value
                    break
    except (TypeError, ValueError):
        kwargs = {}

    if len(kwargs) >= 3:
        return await cli.sign_in(**kwargs)

    # standard Pyrogram 1.x / 2.x keyword names (fallback)
    return await cli.sign_in(
        phone_number=phone_number,
        phone_code_hash=phone_code_hash,
        phone_code=phone_code,
    )


def _temp_helper_client() -> Client:
    return Client(
        name="helper",
        api_id=cfg.API_ID,
        api_hash=cfg.API_HASH,
        workdir=cfg.SESSION_DIR,
        device_model="MusicRasool Helper",
        app_version="1.0.0",
        in_memory=False,
    )


@app.on_message(filters.private & filters.text, group=1)
async def login_flow(client, m: Message):
    uid = m.from_user.id if m.from_user else m.chat.id
    state = LOGIN_STATE.get(uid)
    if state is None:
        # no active login wizard - let other handlers process this message
        raise ContinuePropagation
    text = (m.text or "").strip()
    # commands (e.g. the /login message itself) must never be consumed
    # as a phone number / code / password by the wizard
    if text.startswith("/"):
        raise ContinuePropagation

    if state["step"] == "phone":
        if not text.startswith("+"):
            return await m.reply(
                i18n.t(uid, "• لطفا شماره را با + و کد کشور وارد کنید !", "• Please enter the number with + and country code !")
            )
        state["phone"] = text
        state["step"] = "code"
        state["client"] = _temp_helper_client()
        try:
            await state["client"].connect()
            sent = await state["client"].send_code(text)
            state["phone_code_hash"] = sent.phone_code_hash
        except PhoneNumberInvalid:
            await state["client"].disconnect()
            LOGIN_STATE.pop(uid, None)
            return await m.reply(
                i18n.t(uid, "❌ شماره تلفن معتبر نیست !", "❌ Phone number is invalid !")
            )
        except Exception as exc:
            logger.exception("send_code failed")
            try:
                await state["client"].disconnect()
            except Exception:
                pass
            LOGIN_STATE.pop(uid, None)
            return await m.reply(
                i18n.t(
                    uid,
                    "❌ ارسال کد با مشکل مواجه شد !\n`{}`",
                    "❌ Failed to send the code !\n`{}`",
                ).format(exc)
            )
        await m.reply(
            i18n.t(
                uid,
                "🔑 **مرحله ۲ از ۳**\n"
                "کد ورود که به تلفن/تلگرام حساب هلپر ارسال شده را وارد کنید :",
                "🔑 **Step 2 of 3**\n"
                "Enter the login code sent to the Helper account's phone/Telegram :",
            )
        )
        return

    if state["step"] == "code":
        cli = state.get("client")
        phone = state.get("phone")
        try:
            # signature-adaptive: never mixes positional+keyword, so the
            # "multiple values for argument" TypeError cannot happen
            await _do_sign_in(cli, phone, state.get("phone_code_hash"), text)
        except TypeError as exc:
            # defensive: should never trigger, but keep the wizard alive
            logger.warning("sign_in TypeError: %s", exc)
            return await m.reply(
                i18n.t(
                    uid,
                    "❌ خطای داخلی در فراخوانی ورود (`{}`).\nلطفا یک بار دیگر تلاش کنید یا `sessions/helper.session` را حذف و از ابتدا شروع کنید.",
                    "❌ Internal error while signing in (`{}`).\nPlease retry, or delete `sessions/helper.session` and start over.",
                ).format(exc)
            )
        except SessionPasswordNeeded:
            state["step"] = "password"
            return await m.reply(
                i18n.t(
                    uid,
                    "🔐 **مرحله ۳ از ۳**\nحساب هلپر دارای رمز دو مرحله‌ای است. رمز عبور را وارد کنید :",
                    "🔐 **Step 3 of 3**\nThe Helper account has two-step verification enabled. Enter the password :",
                )
            )
        except (PhoneCodeInvalid, PhoneCodeExpired):
            return await m.reply(
                i18n.t(uid, "❌ کد وارد شده صحیح نیست. دوباره تلاش کنید :", "❌ The code is wrong. Try again :")
            )
        except BadRequest as exc:
            return await m.reply(
                i18n.t(uid, "❌ خطا : `{}`", "❌ Error : `{}`").format(exc)
            )
        except Exception as exc:
            logger.exception("sign_in failed")
            return await m.reply(
                i18n.t(uid, "❌ خطا : `{}`", "❌ Error : `{}`").format(exc)
            )
        try:
            await cli.disconnect()
        except Exception:
            pass
        LOGIN_STATE.pop(uid, None)
        return await _login_done(client, m)

    if state["step"] == "password":
        cli = state.get("client")
        try:
            await cli.check_password(text)
        except BadRequest as exc:
            return await m.reply(
                i18n.t(uid, "❌ رمز عبور اشتباه است. دوباره تلاش کنید :", "❌ Wrong password. Try again :")
            )
        except Exception as exc:
            logger.exception("check_password failed")
            return await m.reply(
                i18n.t(uid, "❌ خطا : `{}`", "❌ Error : `{}`").format(exc)
            )
        try:
            await cli.disconnect()
        except Exception:
            pass
        LOGIN_STATE.pop(uid, None)
        return await _login_done(client, m)


async def _login_done(client, m: Message):
    uid = m.from_user.id if m.from_user else m.chat.id
    try:
        me = await client.get_me()
        first_name = me.first_name
    except Exception:
        first_name = "Helper"
    await m.reply(
        i18n.t(
            uid,
            "✅ **حساب هلپر با موفقیت وارد شد !**\n"
            f"نام حساب : {first_name}\n\n"
            "برای فعال شدن حساب هلپر، دستور `/restart` را ارسال کنید.",
            "✅ **Helper account logged in successfully !**\n"
            f"Account name : {first_name}\n\n"
            "Send `/restart` to activate the helper account.",
        )
    )
