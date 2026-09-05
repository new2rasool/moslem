"""
Player control callbacks: pause / resume / stop / mute / close
buttons on the now-playing cards (music / video / playlist variants).
"""
import os

from pyrogram.types import CallbackQuery

import config
import database
import i18n
import utils
from clients import app, call_py

cfg = config.get_config()
OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID


def _music_access(chat_id):
    return [*database.allmusic(), *database.allvideo(), *database.idsudos(), *database.idowner(),
            *database.creators(chat_id), *database.idmusic(chat_id), *database.idvideo(chat_id), SUDO, OWNER]


def _video_access(chat_id):
    return [*database.allvideo(), *database.allmusic(), *database.idsudos(), *database.idowner(),
            *database.creators(chat_id), *database.idmusic(chat_id), *database.idvideo(chat_id), SUDO, OWNER]


async def handle_player(client, m: CallbackQuery, data: str):
    """Player control buttons.

    NOTE: `"a"` (now-playing indicator) and `"clzz"` (close the language
    panel) are answered in callbacks/router.py *before* routing reaches here,
    so they are deliberately not handled in this module - the previous copies
    of those two branches were unreachable.
    """
    uid = m.from_user.id
    chat_id = m.message.chat.id
    playing = utils.PLAYING
    playlis = utils.PLAYLIS

    # ---- music buttons ----
    if data in ("pausee", "resumee", "closee", "mutemus", "unmutemus", "cls"):
        access = _music_access(chat_id)
        if uid not in access:
            return False
        if data == "pausee":
            if chat_id in playing and uid in access:
                await call_py.pause_stream(chat_id)
                await m.answer(i18n.t(uid, "• پخش با موفقیت مکث شد !", "• Playback paused !"), show_alert=True)
                return True
        if data == "resumee":
            if chat_id in playing and uid in access:
                await call_py.resume_stream(chat_id)
                await m.answer(i18n.t(uid, "• پخش با موفقیت از سرگیری شد !", "• Playback resumed !"), show_alert=True)
                return True
        if data == "closee":
            if chat_id in playing and uid in access:
                old = utils.clear_streaming(chat_id)
                if old and os.path.isfile(str(old)):
                    try:
                        os.remove(old)
                    except Exception:
                        pass
                try:
                    await call_py.leave_group_call(chat_id)
                except Exception:
                    pass
                await m.answer(i18n.t(uid, "• پخش با موفقیت متوقف شد !", "• Playback stopped !"), show_alert=True)
                try:
                    await m.message.delete()
                except Exception:
                    pass
                return True
        if data == "mutemus":
            await call_py.mute_stream(chat_id)
            await m.answer(i18n.t(uid, "• پخش بیصدا شد !", "• Muted !"))
            return True
        if data == "unmutemus":
            await call_py.unmute_stream(chat_id)
            await m.answer(i18n.t(uid, "• پخش با صدا شد !", "• Unmuted !"))
            return True
        if data == "cls":
            if chat_id in playing and uid in access:
                try:
                    await m.message.delete()
                except Exception:
                    pass
                await m.answer(i18n.t(uid, "• پنل با موفقیت بسته شد !", "• Panel closed !"), show_alert=True)
                return True

    # ---- playlist buttons ----
    if data in ("pauseee", "resumeee", "closeee"):
        access = _music_access(chat_id)
        if uid not in access:
            return False
        if data == "pauseee":
            if chat_id in playlis:
                await call_py.pause_stream(chat_id)
                await m.answer(i18n.t(uid, "• پخش با موفقیت مکث شد !", "• Playback paused !"), show_alert=True)
                return True
        if data == "resumeee":
            if chat_id in playlis:
                await call_py.resume_stream(chat_id)
                await m.answer(i18n.t(uid, "• پخش با موفقیت از سرگیری شد !", "• Playback resumed !"), show_alert=True)
                return True
        if data == "closeee":
            if chat_id in playlis:
                playlis.pop(chat_id, None)
                try:
                    await call_py.leave_group_call(chat_id)
                except Exception:
                    pass
                from handlers.playback import PLAYLIST_TASKS
                task = PLAYLIST_TASKS.pop(chat_id, None)
                if task:
                    task.cancel()
                await m.answer(i18n.t(uid, "• پخش با موفقیت متوقف شد !", "• Playback stopped !"), show_alert=True)
                try:
                    await m.message.delete()
                except Exception:
                    pass
                return True

    # ---- video buttons ----
    if data in ("pauseeee", "resumeeee", "closeeee", "mutevid", "unmutevid", "clls"):
        access = _video_access(chat_id)
        if uid not in access:
            return False
        if data == "pauseeee":
            if chat_id in playing:
                await call_py.pause_stream(chat_id)
                await m.answer(i18n.t(uid, "• پخش با موفقیت مکث شد !", "• Playback paused !"), show_alert=True)
                return True
        if data == "resumeeee":
            if chat_id in playing:
                await call_py.resume_stream(chat_id)
                await m.answer(i18n.t(uid, "• پخش با موفقیت از سرگیری شد !", "• Playback resumed !"), show_alert=True)
                return True
        if data == "closeeee":
            if chat_id in playing:
                old = utils.clear_streaming(chat_id)
                if old and os.path.isfile(str(old)):
                    try:
                        os.remove(old)
                    except Exception:
                        pass
                try:
                    await call_py.leave_group_call(chat_id)
                except Exception:
                    pass
                await m.answer(i18n.t(uid, "• پخش با موفقیت متوقف شد !", "• Playback stopped !"), show_alert=True)
                try:
                    await m.message.delete()
                except Exception:
                    pass
                return True
        if data == "mutevid":
            await call_py.mute_stream(chat_id)
            await m.answer(i18n.t(uid, "• پخش بیصدا شد !", "• Muted !"))
            return True
        if data == "unmutevid":
            await call_py.unmute_stream(chat_id)
            await m.answer(i18n.t(uid, "• پخش با صدا شد !", "• Unmuted !"))
            return True
        if data == "clls":
            if chat_id in playing:
                try:
                    await m.message.delete()
                except Exception:
                    pass
                await m.answer(i18n.t(uid, "• پنل با موفقیت بسته شد !", "• Panel closed !"), show_alert=True)
                return True

    return False
