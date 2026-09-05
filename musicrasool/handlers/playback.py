"""
Playback handlers: play / pause / resume / stop / volume, playlists,
search & autoplay (Melobit), YouTube search & direct URL playback.
"""
import asyncio
import os

from pyrogram import filters, enums
from pyrogram.types import Message
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty

import config
import database
import i18n
import utils
from clients import app, call_py, helper_ready
from pytgcalls.types.stream.legacy import AudioPiped, AudioVideoPiped
from pytgcalls.types.raw import VideoParameters

cfg = config.get_config()
OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID

PLAYING = utils.PLAYING
PLAYLIS = utils.PLAYLIS

PLAYLIST_TASKS = {}   # chat_id -> asyncio.Task
SKIP_EVENT = {}       # chat_id -> asyncio.Event (used by /skip)


# ----------------------------------------------------------------------
# Shared helpers
# ----------------------------------------------------------------------
async def require_helper(uid, m):
    if not helper_ready():
        await m.reply(
            i18n.t(
                uid,
                "⚠️ حساب هلپر وارد نشده است !\nلطفا با پشتیبانی تماس بگیرید (دستور /login مخصوص مدیر).",
                "⚠️ The helper account is not logged in !\nPlease contact support (/login is for the admin).",
            )
        )
        return False
    return True


async def stop_current(chat_id):
    try:
        await call_py.leave_group_call(chat_id)
    except Exception:
        pass
    old = utils.clear_streaming(chat_id)
    if old and os.path.isfile(str(old)):
        try:
            os.remove(old)
        except Exception:
            pass


async def _del(message):
    """Delete a transient status message, ignoring any failure."""
    if message is None:
        return
    try:
        await message.delete()
    except Exception:
        pass


def _download_failed(uid, why):
    """User-facing download error that includes the real reason.

    Every failure used to collapse into the same "Download failed !" string,
    which made it impossible to tell "yt-dlp is not installed" from
    "this video is private" from "ffmpeg is missing".
    """
    reason = (why or "").strip()
    if reason:
        return i18n.t(uid, f"• عملیات دانلود با شکست مواجه شد !\n`{reason}`",
                           f"• Download failed !\n`{reason}`")
    return i18n.t(uid, "• عملیات دانلود با شکست مواجه شد !", "• Download failed !")


async def _resolve_stream_url(url: str, chat_id: int, uid: int, msg_id: int, video: bool):
    """Turn any playable URL into a local file, with the reason if that fails.

    Returns (path, title, resolution, error). All four link commands
    (`پخش لینک`, `پخش لینک ویدیو`, `/play`, `/playvideo`) used to hand the raw
    URL to ffmpeg, which has no YouTube demuxer at all and always assumed
    640x360 for video.
    """
    youtube = utils.is_youtube_link(url)
    tag = ("ytv" if video else "yta") if youtube else ("lnkv" if video else "lnka")
    prefix = f"{tag}_{chat_id}_{uid}_{msg_id}"
    if youtube:
        info = await utils.ytdlp_info(url)
        title = (info or {}).get("title") or "YouTube"
        path, why = await utils.ytdlp_download(url, prefix, video=video)
        if not path:
            return None, title, None, why
    else:
        suffix = os.path.splitext(url.split("?")[0])[1][:8] or (".mp4" if video else ".mp3")
        path, why = await utils.download_url(url, prefix, suffix)
        if not path:
            return None, "—", None, why
        title = "—"
    resolution, _duration = await utils.probe_media(path)
    return path, title, resolution, None


def media_name(m):
    audio = m.audio
    if audio:
        return (audio.file_name or "Unknown").replace(".mp3", "")
    if m.voice:
        return i18n.t(m.from_user.id if m.from_user else 0, "ویس", "Voice")
    return "Unknown"


def _media_ext(message) -> str:
    """Best-guess file extension for a replied media message."""
    if message.audio and message.audio.file_name:
        ext = os.path.splitext(message.audio.file_name)[1]
        if ext:
            return ext[:8]
    if message.voice:
        return ".ogg"
    if message.video and message.video.file_name:
        ext = os.path.splitext(message.video.file_name)[1]
        if ext:
            return ext[:8]
    if message.video:
        return ".mp4"
    return ".mp3"


async def _download_media(client, message, uid, prefix, status_msg=None):
    """Download replied media to disk - large-file friendly.

    - preserves the original extension,
    - verifies the result is a non-empty file,
    - retries once on failure/partial download.
    Returns the local path or None.
    """
    folder = cfg.DOWNLOAD_DIR
    os.makedirs(folder, exist_ok=True)
    ext = _media_ext(message)
    base = os.path.join(folder, f"{prefix}_{message.chat.id}_{uid}_{message.id}")
    candidates = [base + ext, base + "_r" + ext]

    for i, name in enumerate(candidates):
        try:
            if os.path.exists(name):
                try:
                    os.remove(name)
                except Exception:
                    pass
        except Exception:
            pass
        try:
            out = await client.download_media(message, file_name=name)
        except Exception as exc:
            print("download failed (try %d): %s" % (i + 1, exc))
            out = None
        if out and os.path.isfile(out) and os.path.getsize(out) > 0:
            if status_msg is not None:
                try:
                    await status_msg.delete()
                except Exception:
                    pass
            return out
        # partial/empty -> remove and retry
        try:
            if out and os.path.exists(out):
                os.remove(out)
        except Exception:
            pass
        if status_msg is not None:
            try:
                await status_msg.edit(
                    i18n.t(uid, "**⌯** دانلود مجدد ...", "**⌯** Retrying download ...")
                )
            except Exception:
                pass
    if status_msg is not None:
        try:
            await status_msg.delete()
        except Exception:
            pass
    return None


async def play_audio(client, m, path, extra_title="", duration=None):
    """Stream an audio file/URL in the chat voice call."""
    uid = m.from_user.id
    chat_id = m.chat.id
    await stop_current(chat_id)
    await utils.join_with_retry(chat_id, AudioPiped(path), tries=2)
    utils.mark_streaming(chat_id, "audio", path, duration=duration)
    a = utils.jalali_now()
    fa = (
        f"**⌯** **موزیک در حال پخش میباشد** **🔊**\n"
        f"**⊹** نام موزیک : {extra_title}\n"
        f"**⊹** نام درخواست کننده : {m.from_user.mention(m.from_user.first_name)}\n"
        f"**⊹** شناسه گروه : `{chat_id}`\n"
        f"**⊹** ساعت : `{a}` 🕦"
    )
    en = (
        f"**⌯** **Now Playing** **🔊**\n"
        f"**⊹** Music : {extra_title}\n"
        f"**⊹** Requested by : {m.from_user.mention(m.from_user.first_name)}\n"
        f"**⊹** Group id : `{chat_id}`\n"
        f"**⊹** Time : `{a}` 🕦"
    )
    await utils.send_card(
        client, chat_id, uid, fa, en,
        reply_markup=utils.player_keyboard(uid, "music"),
        reply_to_message_id=m.id,
    )


async def play_video(client, m, path, extra_title="", resolution=None, reply_id=None, duration=None):
    """Stream a video file/URL in the chat voice call."""
    uid = m.from_user.id
    chat_id = m.chat.id
    await stop_current(chat_id)
    if resolution is None and os.path.isfile(path):
        # Without a resolution the legacy VideoParameters() default (640x360)
        # was used, so every video coming from a link/YouTube was downscaled to
        # 360p regardless of its real size.
        resolution, _probed_dur = await utils.probe_media(path)
    if resolution:
        stream = AudioVideoPiped(path, video_parameters=VideoParameters(*resolution))
    else:
        stream = AudioVideoPiped(path)
    await utils.join_with_retry(chat_id, stream, tries=2)
    utils.mark_streaming(chat_id, "video", path, resolution, duration=duration)
    a = utils.jalali_now()
    fa = (
        f"**⌯** **ویدیو در حال پخش میباشد** **🔊**\n"
        f"**⊹** نام ویدیو : {extra_title or '—'}\n"
        f"**⊹** نام درخواست کننده : {m.from_user.mention(m.from_user.first_name)}\n"
        f"**⊹** شناسه گروه : `{chat_id}`\n"
        f"**⊹** ساعت : `{a}` 🕦"
    )
    en = (
        f"**⌯** **Now Playing** **🔊**\n"
        f"**⊹** Video : {extra_title or '—'}\n"
        f"**⊹** Requested by : {m.from_user.mention(m.from_user.first_name)}\n"
        f"**⊹** Group id : `{chat_id}`\n"
        f"**⊹** Time : `{a}` 🕦"
    )
    await utils.send_card(
        client, chat_id, uid, fa, en,
        reply_markup=utils.player_keyboard(uid, "video"),
        reply_to_message_id=reply_id or m.id,
    )


async def play_dedicated_music(client, m, path, target_chat, title, duration=None):
    """Play an audio dedicated to a user (original behavior)."""
    uid = m.from_user.id
    chat_id = m.chat.id
    await stop_current(chat_id)
    await utils.join_with_retry(chat_id, AudioPiped(path), tries=2)
    utils.mark_streaming(chat_id, "audio", path, duration=duration)
    a = utils.jalali_now()
    fa = (
        f"<b>⌯ موزیک تقدیمی به {target_chat.first_name} در حال پخش میباشد 🔊 </b>\n"
        f"<b>⊹</b> نام موزیک : {title}\n"
        f"<b>⊹</b> از طرف : {m.from_user.mention(m.from_user.first_name)}\n"
        f"<b>⊹</b> تقدیم به :  <a href=tg://user?id={target_chat.id}>{target_chat.first_name}</a>\n"
        f"<b>⊹</b> ساعت : <code>{a}</code> 🕦"
    )
    en = (
        f"<b>⌯ Music dedicated to {target_chat.first_name} is now playing 🔊 </b>\n"
        f"<b>⊹</b> Music : {title}\n"
        f"<b>⊹</b> From : {m.from_user.mention(m.from_user.first_name)}\n"
        f"<b>⊹</b> For :  <a href=tg://user?id={target_chat.id}>{target_chat.first_name}</a>\n"
        f"<b>⊹</b> Time : <code>{a}</code> 🕦"
    )
    await utils.send_card(
        client, chat_id, uid, fa, en,
        reply_markup=utils.player_keyboard(uid, "music"),
        reply_to_message_id=m.id,
        parse_mode=enums.ParseMode.HTML,
    )


async def play_dedicated_video(client, m, path, target_chat, resolution=None, duration=None):
    uid = m.from_user.id
    chat_id = m.chat.id
    await stop_current(chat_id)
    if resolution is None and os.path.isfile(path):
        # Without a resolution the legacy VideoParameters() default (640x360)
        # was used, so every video coming from a link/YouTube was downscaled to
        # 360p regardless of its real size.
        resolution, _probed_dur = await utils.probe_media(path)
    if resolution:
        stream = AudioVideoPiped(path, video_parameters=VideoParameters(*resolution))
    else:
        stream = AudioVideoPiped(path)
    await utils.join_with_retry(chat_id, stream, tries=2)
    utils.mark_streaming(chat_id, "video", path, resolution, duration=duration)
    a = utils.jalali_now()
    fa = (
        f"<b>⌯ ویدیو تقدیمی به {target_chat.first_name} در حال پخش میباشد 🔊</b>\n"
        f"<b>⊹</b> از طرف : {m.from_user.mention(m.from_user.first_name)}\n"
        f"<b>⊹</b> تقدیم به :  <a href=tg://user?id={target_chat.id}>{target_chat.first_name}</a>\n"
        f"<b>⊹</b> ساعت : <code>{a}</code> 🕦"
    )
    en = (
        f"<b>⌯ Video dedicated to {target_chat.first_name} is now playing 🔊</b>\n"
        f"<b>⊹</b> From : {m.from_user.mention(m.from_user.first_name)}\n"
        f"<b>⊹</b> For :  <a href=tg://user?id={target_chat.id}>{target_chat.first_name}</a>\n"
        f"<b>⊹</b> Time : <code>{a}</code> 🕦"
    )
    await utils.send_card(
        client, chat_id, uid, fa, en,
        reply_markup=utils.player_keyboard(uid, "video"),
        reply_to_message_id=m.id,
        parse_mode=enums.ParseMode.HTML,
    )


# ----------------------------------------------------------------------
# پخش / play (reply to audio, or dedicate: reply + @user)
# ----------------------------------------------------------------------
@app.on_message(filters.group & filters.reply & (filters.regex(r"^(پخش)$") | filters.regex(r"^([Pp][Ll][Aa][Yy])$")))
async def play_reply(client, m: Message):
    uid = m.from_user.id
    horn = [*database.moz(1), *database.moz(0)]
    access = utils.music_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insmusic():
        return
    if not (m.reply_to_message.audio or m.reply_to_message.voice):
        return
    if not await require_helper(uid, m):
        return
    status = await m.reply(
        i18n.t(uid, "**⌯** در حال دانلود ... **⌯**", "**⌯** Downloading ... **⌯**")
    )
    path = await _download_media(client, m.reply_to_message, uid, "mus", status)
    if not path:
        return await m.reply(
            i18n.t(uid, "• دانلود فایل با مشکل مواجه شد !", "• Failed to download the file !")
        )
    dur = None
    if m.reply_to_message.audio and m.reply_to_message.audio.duration:
        dur = m.reply_to_message.audio.duration
    elif m.reply_to_message.voice and m.reply_to_message.voice.duration:
        dur = m.reply_to_message.voice.duration
    print("Playing {} in {}".format(path, m.chat.title))
    try:
        await play_audio(client, m, path, media_name(m.reply_to_message), duration=dur)
    except Exception as exc:
        print(exc)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))


# NOTE: this handler is registered BEFORE playvideo_reply / playvideo_dedicate /
# play_file_cmd and all three share the "پخش " prefix, so every one of them has
# to appear in the negative lookahead. `ویدیو` and `فایل` were missing, which
# meant that replying to a video and sending "پخش ویدیو" (or "پخش ویدیو @user")
# was swallowed here and ended in a "user not found" error instead of playing.
@app.on_message(filters.group & filters.reply & (
    filters.regex(r"^(پخش )(?!لینک|یوتیوب|خودکار|لیست|ویدیو|فایل)")
    | filters.regex(r"^([Pp][Ll][Aa][Yy]) (?! ?[Vv]ideo| ?[Ff]ile| ?[Ll]ink| ?[Aa]uto| ?[Ll]ist| ?[Yy]ou)")
))
async def play_dedicate(client, m: Message):
    uid = m.from_user.id
    horn = [*database.moz(1), *database.moz(0)]
    access = utils.music_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    text = utils.msg_text(m)
    text = text.replace("پخش", "")
    try:
        text = utils.clean_command(text, "", "Play")
    except Exception:
        pass
    text = text.strip().lstrip("@")
    if not text:
        return
    # a URL after "پخش" behaves like "پخش لینک"
    if text.startswith("http"):
        if await utils.checkjoin(client, m, uid) is not None:
            return
        if m.chat.id not in database.insmusic():
            return
        if not await require_helper(uid, m):
            return
        status = await m.reply(i18n.t(uid, "**⌯** در حال دریافت ... **⌯**", "**⌯** Fetching ... **⌯**"))
        try:
            path, title, _resolution, err = await _resolve_stream_url(text, m.chat.id, uid, m.id, False)
            if not path:
                await _del(status)
                return await m.reply(_download_failed(uid, err))
            await _del(status)
            print("Playing {} in {}".format(path, m.chat.title))
            await play_audio(client, m, path, title)
        except Exception as exc:
            print(exc)
            await _del(status)
            await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))
        return
    target = await utils.resolve_chat(text)
    if target is None:
        return await m.reply(i18n.t(uid, "• کاربر مورد نظر یافت نشد !", "• The requested user was not found !"))
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insmusic():
        return
    if not (m.reply_to_message.audio or m.reply_to_message.voice):
        return
    if not await require_helper(uid, m):
        return
    status = await m.reply(
        i18n.t(uid, "**⌯** در حال دانلود ... **⌯**", "**⌯** Downloading ... **⌯**")
    )
    path = await _download_media(client, m.reply_to_message, uid, "ded", status)
    if not path:
        return await m.reply(
            i18n.t(uid, "• دانلود فایل با مشکل مواجه شد !", "• Failed to download the file !")
        )
    dur = None
    if m.reply_to_message.audio and m.reply_to_message.audio.duration:
        dur = m.reply_to_message.audio.duration
    elif m.reply_to_message.voice and m.reply_to_message.voice.duration:
        dur = m.reply_to_message.voice.duration
    print("Playing {} in {}".format(path, m.chat.title))
    try:
        await play_dedicated_music(client, m, path, target, media_name(m.reply_to_message), duration=dur)
    except Exception as exc:
        print(exc)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))


# ----------------------------------------------------------------------
# پخش ویدیو / playvideo (reply video, or dedicate)
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(پخش ویدیو)$") | filters.regex(r"^([Pp][Ll][Aa][Yy][Vv][Ii][Dd][Ee][Oo])$")))
async def playvideo_reply(client, m: Message):
    uid = m.from_user.id
    horn = [*database.kir(1), *database.kir(0)]
    access = utils.video_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insvideo():
        return
    if not (m.reply_to_message and m.reply_to_message.video):
        return
    if not await require_helper(uid, m):
        return
    status = await m.reply(
        i18n.t(uid, "**⌯** در حال دانلود ... **⌯**", "**⌯** Downloading ... **⌯**")
    )
    path = await _download_media(client, m.reply_to_message, uid, "vid", status)
    if not path:
        return await m.reply(
            i18n.t(uid, "• دانلود فایل با مشکل مواجه شد !", "• Failed to download the file !")
        )
    video = m.reply_to_message.video
    resolution = [video.width, video.height]
    dur = video.duration or None
    print("Playing {} in {}".format(path, m.chat.title))
    try:
        await play_video(client, m, path, "—", resolution=resolution, reply_id=m.reply_to_message.id, duration=dur)
    except Exception as exc:
        print(exc)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))


@app.on_message(filters.group & (filters.regex(r"^(پخش ویدیو )") | filters.regex(r"^([Pp][Ll][Aa][Yy][Vv][Ii][Dd][Ee][Oo]) ")))
async def playvideo_dedicate(client, m: Message):
    uid = m.from_user.id
    horn = [*database.kir(1), *database.kir(0)]
    access = utils.video_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    text = utils.msg_text(m).replace("پخش ویدیو", "")
    try:
        text = utils.clean_command(text, "", "PlayVideo")
    except Exception:
        pass
    text = text.strip().lstrip("@")
    if not text:
        return
    target = await utils.resolve_chat(text)
    if target is None:
        return await m.reply(i18n.t(uid, "• کاربر مورد نظر یافت نشد !", "• The requested user was not found !"))
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insvideo():
        return
    if not (m.reply_to_message and m.reply_to_message.video):
        return
    if not await require_helper(uid, m):
        return
    status = await m.reply(
        i18n.t(uid, "**⌯** در حال دانلود ... **⌯**", "**⌯** Downloading ... **⌯**")
    )
    path = await _download_media(client, m.reply_to_message, uid, "dvid", status)
    if not path:
        return await m.reply(
            i18n.t(uid, "• دانلود فایل با مشکل مواجه شد !", "• Failed to download the file !")
        )
    video = m.reply_to_message.video
    resolution = [video.width, video.height]
    dur = video.duration or None
    print("Playing {} in {}".format(path, m.chat.title))
    try:
        await play_dedicated_video(client, m, path, target, resolution, duration=dur)
    except Exception as exc:
        print(exc)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))


# ----------------------------------------------------------------------
# پخش لینک / playlink (audio) and پخش لینک ویدیو / playlinkvideo
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(پخش لینک ویدیو)") | filters.regex(r"^([Pp][Ll][Aa][Yy][Ll][Ii][Nn][Kk][Vv][Ii][Dd][Ee][Oo])")))
async def play_link_video(client, m: Message):
    uid = m.from_user.id
    horn = [*database.kir(1), *database.kir(0)]
    access = utils.video_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    text = utils.clean_command(utils.msg_text(m), "پخش لینک ویدیو", "PlayLinkVideo").strip()
    # the old check only looked for the literal strings ".mp4"/".mkv" in the
    # URL, so anything else (.webm, .mov, a link with a query string, a
    # YouTube link) was refused as "not a video link" without a single attempt.
    if not text.startswith("http"):
        return await m.reply(i18n.t(uid, "این لینک دانلود ویدیو نیست و امکان پخش وجود ندارد !", "This is not a video download link and cannot be played !"))
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insvideo():
        return
    if not await require_helper(uid, m):
        return
    status = await m.reply(i18n.t(uid, "**⌯** در حال دریافت ... **⌯**", "**⌯** Fetching ... **⌯**"))
    try:
        path, title, resolution, err = await _resolve_stream_url(text, m.chat.id, uid, m.id, True)
        if not path:
            await _del(status)
            return await m.reply(_download_failed(uid, err))
        await _del(status)
        print("Playing {} in {}".format(path, m.chat.title))
        await play_video(client, m, path, title, resolution=resolution)
    except Exception as exc:
        print(exc)
        await _del(status)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))


@app.on_message(filters.group & (filters.regex(r"^(پخش لینک)(?! ویدیو)") | filters.regex(r"^([Pp][Ll][Aa][Yy][Ll][Ii][Nn][Kk])(?! ?[Vv]ideo)")))
async def play_link(client, m: Message):
    uid = m.from_user.id
    horn = [*database.moz(1), *database.moz(0)]
    access = utils.music_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    text = utils.clean_command(utils.msg_text(m), "پخش لینک", "PlayLink").strip()
    if "http" not in text:
        return await m.reply(i18n.t(uid, "• لینک معتبر نیست !", "• Invalid link !"))
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insmusic():
        return
    if not await require_helper(uid, m):
        return
    status = await m.reply(i18n.t(uid, "**⌯** در حال دریافت ... **⌯**", "**⌯** Fetching ... **⌯**"))
    try:
        path, title, _resolution, err = await _resolve_stream_url(text, m.chat.id, uid, m.id, False)
        if not path:
            await _del(status)
            return await m.reply(_download_failed(uid, err))
        await _del(status)
        print("Playing {} in {}".format(path, m.chat.title))
        await play_audio(client, m, path, title)
    except Exception as exc:
        print(exc)
        await _del(status)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))


# ----------------------------------------------------------------------
# توقف پخش / stopmusic & توقف ویدیو / stopvideo
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(توقف پخش)$") | filters.regex(r"^([Ss][Tt][Oo][Pp][Mm][Uu][Ss][Ii][Cc])$")))
async def stopmusic(client, m: Message):
    uid = m.from_user.id
    access = [*database.allmusic(), *database.allvideo(), *database.idsudos(), *database.idowner(),
              *database.creators(m.chat.id), SUDO, OWNER]
    if uid not in access:
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id in PLAYING:
        old = utils.clear_streaming(m.chat.id)
        if old and os.path.isfile(str(old)):
            try:
                os.remove(old)
            except Exception:
                pass
        try:
            await call_py.leave_group_call(m.chat.id)
        except Exception:
            pass
        a = utils.jalali_now()
        fa = (
            f"**⌯** **پخش موزیک متوقف شد** **🔇**\n\n"
            f"**⊹** نام درخواست کننده : {m.from_user.mention(m.from_user.first_name)}\n"
            f"**⊹** شناسه گروه : `{m.chat.id}`\n"
            f"**⊹** ساعت : `{a}` 📅"
        )
        en = (
            f"**⌯** **Music playback stopped** **🔇**\n"
            f"**⊹** Requested by : {m.from_user.mention(m.from_user.first_name)}\n"
            f"**⊹** Group id : `{m.chat.id}`\n"
            f"**⊹** Time : `{a}` 📅"
        )
        await utils.send_card(client, m.chat.id, uid, fa, en, reply_to_message_id=m.id)


@app.on_message(filters.group & (filters.regex(r"^(توقف ویدیو)$") | filters.regex(r"^([Ss][Tt][Oo][Pp][Vv][Ii][Dd][Ee][Oo])$")))
async def stopvideo(client, m: Message):
    uid = m.from_user.id
    access = [*database.idsudos(), *database.idowner(), *database.idvideo(m.chat.id),
              *database.creators(m.chat.id), SUDO, OWNER, *database.allvideo()]
    if uid not in access:
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id in PLAYING:
        old = utils.clear_streaming(m.chat.id)
        if old and os.path.isfile(str(old)):
            try:
                os.remove(old)
            except Exception:
                pass
        try:
            await call_py.leave_group_call(m.chat.id)
        except Exception:
            pass
        a = utils.jalali_now()
        fa = (
            f"**⌯** **پخش ویدیو متوقف شد** **🔇**\n\n"
            f"**⊹** نام درخواست کننده : {m.from_user.mention(m.from_user.first_name)}\n"
            f"**⊹** شناسه گروه : `{m.chat.id}`\n"
            f"**⊹** ساعت : `{a}` 📅"
        )
        en = (
            f"**⌯** **Video playback stopped** **🔇**\n"
            f"**⊹** Requested by : {m.from_user.mention(m.from_user.first_name)}\n"
            f"**⊹** Group id : `{m.chat.id}`\n"
            f"**⊹** Time : `{a}` 📅"
        )
        await utils.send_card(client, m.chat.id, uid, fa, en, reply_to_message_id=m.id)


# ----------------------------------------------------------------------
# مکث / pause & ازسرگیری / resume
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(مکث)$") | filters.regex(r"^([Pp][Aa][Uu][Ss][Ee])$")))
async def pause_cmd(client, m: Message):
    uid = m.from_user.id
    access = [*database.allmusic(), *database.allvideo(), *database.idsudos(), *database.idowner(),
              *database.creators(m.chat.id), SUDO, OWNER]
    if uid in access and (m.chat.id in PLAYING or m.chat.id in PLAYLIS):
        try:
            await call_py.pause_stream(m.chat.id)
            await m.reply(i18n.t(uid, "__**⌯** پخش متوقف شد **!**__", "__**⌯** Playback paused **!**__"))
        except Exception:
            await m.reply(i18n.t(uid, "• مکث با مشکل مواجه شد !", "• Failed to pause !"))


@app.on_message(filters.group & (filters.regex(r"^(ازسرگیری)$") | filters.regex(r"^([Rr][Ee][Ss][Uu][Mm][Ee])$")))
async def resume_cmd(client, m: Message):
    uid = m.from_user.id
    access = [*database.allmusic(), *database.allvideo(), *database.idsudos(), *database.idowner(),
              *database.creators(m.chat.id), SUDO, OWNER]
    if uid in access and (m.chat.id in PLAYING or m.chat.id in PLAYLIS):
        try:
            await call_py.resume_stream(m.chat.id)
            await m.reply(i18n.t(uid, "__**⌯** پخش ازسرگیری شد **!**__", "__**⌯** Playback resumed **!**__"))
        except Exception:
            await m.reply(i18n.t(uid, "• ازسرگیری با مشکل مواجه شد !", "• Failed to resume !"))


# ----------------------------------------------------------------------
# Mute / Unmute: بیصدا / باصدا  (silent / unsilent)
#
# The help panels (callbacks/help.py) have always documented these four
# commands, but muting was only reachable through the inline player buttons
# - there was no text handler at all, so typing them did nothing.
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(بیصدا)$") | filters.regex(r"^([Ss][Ii][Ll][Ee][Nn][Tt])$")))
async def mute_cmd(client, m: Message):
    uid = m.from_user.id
    access = [*database.allmusic(), *database.allvideo(), *database.idsudos(), *database.idowner(),
              *database.creators(m.chat.id), SUDO, OWNER]
    if uid not in access:
        return
    if m.chat.id in PLAYING or m.chat.id in PLAYLIS:
        try:
            await call_py.mute_stream(m.chat.id)
            await m.reply(i18n.t(uid, "__**⌯** پخش بیصدا شد **🔇**__", "__**⌯** Playback muted **🔇**__"))
        except Exception:
            await m.reply(i18n.t(uid, "• بیصدا کردن با مشکل مواجه شد !", "• Failed to mute !"))


@app.on_message(filters.group & (filters.regex(r"^(باصدا)$") | filters.regex(r"^([Uu][Nn][Ss][Ii][Ll][Ee][Nn][Tt])$")))
async def unmute_cmd(client, m: Message):
    uid = m.from_user.id
    access = [*database.allmusic(), *database.allvideo(), *database.idsudos(), *database.idowner(),
              *database.creators(m.chat.id), SUDO, OWNER]
    if uid not in access:
        return
    if m.chat.id in PLAYING or m.chat.id in PLAYLIS:
        try:
            await call_py.unmute_stream(m.chat.id)
            await m.reply(i18n.t(uid, "__**⌯** پخش با صدا شد **🔊**__", "__**⌯** Playback unmuted **🔊**__"))
        except Exception:
            await m.reply(i18n.t(uid, "• باصدا کردن با مشکل مواجه شد !", "• Failed to unmute !"))


# ----------------------------------------------------------------------
# Volume: صدای موزیک / musicsound & صدای ویدیو / videosound
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(صدای موزیک)") | filters.regex(r"^([Mm][Uu][Ss][Ii][Cc][Ss][Oo][Uu][Nn][Dd])")))
async def volume_music(client, m: Message):
    uid = m.from_user.id
    access = utils.music_access(m.chat.id, uid)
    if uid not in access:
        return
    if m.chat.id in PLAYING or m.chat.id in PLAYLIS:
        text = utils.clean_command(m.text, "صدای موزیک", "MusicSound").strip()
        if not utils.is_number(text):
            return await m.reply(i18n.t(uid, "• لطفا یک عدد وارد کنید !", "• Please enter a number !"))
        value = int(text)
        if value < 1 or value > 200:
            return await m.reply(i18n.t(uid, "• لطفا عددی کوچک تر از 200 و بزرگ تر از 0 وارد کنید !", "• Please enter a number between 1 and 200 !"))
        try:
            await call_py.change_volume_call(m.chat.id, value)
            await m.reply(i18n.t(uid, f"**⌯** صدای موزیک به {value} تنظیم شد **!**", f"**⌯** Music volume set to {value} **!**"))
        except Exception:
            await m.reply(i18n.t(uid, "• تغییر صدا با مشکل مواجه شد !", "• Failed to change the volume !"))


@app.on_message(filters.group & (filters.regex(r"^(صدای ویدیو)") | filters.regex(r"^([Vv][Ii][Dd][Ee][Oo][Ss][Oo][Uu][Nn][Dd])")))
async def volume_video(client, m: Message):
    uid = m.from_user.id
    access = utils.video_access(m.chat.id, uid)
    if uid not in access:
        return
    if m.chat.id in PLAYING:
        text = utils.clean_command(m.text, "صدای ویدیو", "VideoSound").strip()
        if not utils.is_number(text):
            return await m.reply(i18n.t(uid, "• لطفا یک عدد وارد کنید !", "• Please enter a number !"))
        value = int(text)
        if value < 1 or value > 200:
            return await m.reply(i18n.t(uid, "• لطفا عددی کوچک تر از 200 و بزرگ تر از 0 وارد کنید !", "• Please enter a number between 1 and 200 !"))
        try:
            await call_py.change_volume_call(m.chat.id, value)
            await m.reply(i18n.t(uid, f"**⌯** صدای ویدیو به {value} تنظیم شد **!**", f"**⌯** Video volume set to {value} **!**"))
        except Exception:
            await m.reply(i18n.t(uid, "• تغییر صدا با مشکل مواجه شد !", "• Failed to change the volume !"))


# ----------------------------------------------------------------------
# سرچ / search (Melobit) - sends the song + cover
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^(سرچ)(?! یوتیوب)") | filters.regex(r"^([Ss][Ee][Aa][Rr][Cc][Hh])")))
async def search_music(client, m: Message):
    uid = m.from_user.id
    horn = [*database.moz(1), *database.moz(0)]
    if m.chat.id not in horn:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in utils.music_access(m.chat.id, uid):
        return
    query = utils.clean_command(m.text, "سرچ", "Search").strip()
    if not query:
        return
    results = await utils.melobit_search(query, 1)
    if not results:
        return await m.reply(i18n.t(uid, "• موزیک مورد نظر یافت نشد !", "• The requested song was not found !"))
    song = results[0]
    info = await utils.melobit_song(song.get("id"))
    if info is None:
        return await m.reply(i18n.t(uid, "• مشکلی برای دانلود موزیک مورد نظر پیش آمده است !", "• There was a problem downloading the song !"))
    download = utils.melobit_download_url(info)
    if not download:
        return await m.reply(i18n.t(uid, "• لینک دانلود یافت نشد !", "• No download link found !"))
    cover = utils.melobit_cover(info)
    ch_rows = database.channel()
    channel_link = ch_rows[0][2] if ch_rows else ""
    mention_music = i18n.t(uid, "🎧 سراسری : جستجوی موزیک 🔍", "🎧 Global : Music search 🔍")
    caption = mention_music if not channel_link else f"[{mention_music}]({channel_link})"
    local = None
    try:
        if cover:
            await client.send_photo(m.chat.id, cover, caption=i18n.t(uid, "♪ کیفیت آهنگ : 320 📀", "♪ Quality : 320 📀"), reply_to_message_id=m.id)
        # a bot may only upload-by-URL files up to 20 MB - fetch first, then
        # upload the local file (limit 50 MB) so long tracks work too
        local = await utils.fetch_media(download, f"search_{m.chat.id}_{m.id}.mp3")
        if not local:
            return await m.reply(i18n.t(uid, "• مشکلی برای دانلود موزیک مورد نظر پیش آمده است !", "• There was a problem downloading the song !"))
        await client.send_audio(m.chat.id, local, caption=caption, title=utils.melobit_title(info), reply_to_message_id=m.id)
    except MediaEmpty:
        await m.reply(i18n.t(uid, "• مشکلی برای دانلود موزیک مورد نظر پیش آمده است !", "• There was a problem downloading the song !"))
    except Exception:
        await m.reply(i18n.t(uid, "• موزیک مورد نظر یافت نشد !", "• The requested song was not found !"))
    finally:
        if local:
            try:
                os.remove(local)
            except OSError:
                pass


# ----------------------------------------------------------------------
# پخش خودکار / autoplay (Melobit search -> play)
# ----------------------------------------------------------------------
# Must be registered BEFORE `autoplay`: pyrogram matches handlers in
# registration order inside a group, and `autoplay`'s regex is the bare prefix
# `^(پخش خودکار)`. Without this handler (and without the `ویدیو` entry in
# `autoplay`'s lookahead) the command `پخش خودکار ویدیو` was swallowed by the
# music autoplay handler and came back as "the requested song was not found".
@app.on_message(filters.group & (
    filters.regex(r"^(پخش خودکار ویدیو)")
    | filters.regex(r"^([Aa][Uu][Tt][Oo][Pp][Ll][Aa][Yy] ?[Vv][Ii][Dd][Ee][Oo])")
))
async def autoplay_video(client, m: Message):
    """`پخش خودکار ویدیو <query>` - search YouTube and play the first video."""
    uid = m.from_user.id
    horn = [*database.kir(1), *database.kir(0)]
    access = utils.video_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insvideo():
        return
    if not await require_helper(uid, m):
        return
    query = utils.clean_command(utils.msg_text(m), "پخش خودکار ویدیو", "AutoPlayVideo").strip()
    if not query:
        return await m.reply(
            i18n.t(uid, "• لطفا نام ویدیو را هم بنویسید !\nمثال : `پخش خودکار ویدیو آهنگ ...`",
                      "• Please include the video name too !\nExample: `AutoPlayVideo <name>`")
        )
    status = await m.reply(
        i18n.t(uid, "**⌯** درحال جستجو و دانلود ویدیو **....**\n┈┅───┤🔎├───┅┈",
               "**⌯** Searching and downloading the video **....**\n┈┅───┤🔎├───┅┈")
    )
    try:
        results = await utils.ytdlp_search(query, 1)
        if not results:
            await _del(status)
            return await m.reply(i18n.t(uid, "• ویدیوی مورد نظر یافت نشد !", "• The requested video was not found !"))
        link = results[0]["url"]
        title = results[0].get("title") or "YouTube"
        path, why = await utils.ytdlp_download(link, f"autov_{m.chat.id}_{uid}_{m.id}", video=True)
        if not path:
            await _del(status)
            return await m.reply(_download_failed(uid, why))
        await _del(status)
        resolution, duration = await utils.probe_media(path)
        print("Playing {} in {}".format(path, m.chat.title))
        await play_video(client, m, path, title, resolution=resolution, duration=duration)
    except Exception as exc:
        print(exc)
        await _del(status)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))


@app.on_message(filters.group & (
    filters.regex(r"^(پخش خودکار)(?! ?ویدیو)")
    | filters.regex(r"^([Aa][Uu][Tt][Oo][Pp][Ll][Aa][Yy])(?! ?[Vv][Ii][Dd][Ee][Oo])")
))
async def autoplay(client, m: Message):
    uid = m.from_user.id
    horn = [*database.moz(1), *database.moz(0)]
    if m.chat.id not in horn:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in utils.music_access(m.chat.id, uid):
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insmusic():
        return
    if not await require_helper(uid, m):
        return
    query = utils.clean_command(m.text, "پخش خودکار", "AutoPlay").strip()
    if not query:
        return
    mm = await m.reply(i18n.t(uid, "**⌯** درحال جستجوی موزیک مورد نظر **....**\n┈┅───┤🔎├───┅┈", "**⌯** Searching for the song **....**\n┈┅───┤🔎├───┅┈"))
    results = await utils.melobit_search(query, 1)
    if not results:
        await mm.delete()
        return await m.reply(i18n.t(uid, "• موزیک مورد نظر یافت نشد !", "• The requested song was not found !"))
    song = results[0]
    info = await utils.melobit_song(song.get("id"))
    if info is None:
        await mm.delete()
        return await m.reply(i18n.t(uid, "• مشکلی برای دانلود موزیک مورد نظر پیش آمده است !", "• There was a problem downloading the song !"))
    download = utils.melobit_download_url(info)
    if not download:
        await mm.delete()
        return await m.reply(i18n.t(uid, "• لینک دانلود یافت نشد !", "• No download link found !"))
    title = utils.melobit_title(info)
    # Download straight into DOWNLOAD_DIR. This used to bounce the file
    # through the helper's Saved Messages (`ubot.send_audio("me", url)`) and
    # then re-download it - which both hit the 20 MB upload-by-URL limit and
    # leaked the message whenever the second half failed.
    path = await utils.fetch_media(download, f"auto_{m.chat.id}_{uid}_{m.id}.mp3")
    if not path:
        try:
            await mm.delete()
        except Exception:
            pass
        return await m.reply(i18n.t(uid, "• مشکلی برای دانلود موزیک مورد نظر پیش آمده است !", "• There was a problem downloading the song !"))

    try:
        try:
            await mm.delete()
        except Exception:
            pass
        dur = await utils.probe_duration(path)
        print("Playing {} in {}".format(path, m.chat.title))
        await play_audio(client, m, path, title, duration=dur)
    except Exception as exc:
        print(exc)
        try:
            await mm.delete()
        except Exception:
            pass


# ----------------------------------------------------------------------
# سرچ یوتیوب / youtubesearch & پخش یوتیوب / youtubeplay
# ----------------------------------------------------------------------
@app.on_message(filters.group & (filters.regex(r"^([Yy][Oo][Uu][Tt][Uu][Bb][Ee][Ss][Ee][Aa][Rr][Cc][Hh])") | filters.regex(r"^(سرچ یوتیوب)")))
async def youtube_search(client, m: Message):
    uid = m.from_user.id
    horn = [*database.kir(1), *database.kir(0)]
    if uid not in utils.video_access(m.chat.id, uid):
        return
    if m.chat.id not in horn:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insvideo():
        return
    if not await require_helper(uid, m):
        return
    query = utils.clean_command(utils.msg_text(m), "سرچ یوتیوب", "YoutubeSearch").strip()
    if not query:
        return
    status = await m.reply(
        i18n.t(uid, "**⌯** در حال جستجو و دانلود از یوتیوب ... **⌯**",
               "**⌯** Searching and downloading from YouTube ... **⌯**")
    )
    try:
        results = await utils.ytdlp_search(query, 1)
        if not results:
            await _del(status)
            return await m.reply(i18n.t(uid, "• ویدیویی یافت نشد !", "• No video found !"))
        link = results[0]["url"]
        title = results[0].get("title") or "YouTube"
        # Download, then stream the local file. Feeding the resolved
        # googlevideo URL straight to ffmpeg used to break: the URL expires,
        # the old `best[...]` selector matched nothing for many videos and the
        # `"googlevideo.com" not in direct` check rejected everything else.
        path, why = await utils.ytdlp_download(
            link, f"ytv_{m.chat.id}_{uid}_{m.id}", video=True
        )
        if not path:
            await _del(status)
            return await m.reply(_download_failed(uid, why))
        await _del(status)
        resolution, duration = await utils.probe_media(path)
        print("Playing {} in {}".format(path, m.chat.title))
        await play_video(client, m, path, title, resolution=resolution, duration=duration)
    except Exception as exc:
        print(exc)
        await _del(status)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))


@app.on_message(filters.group & (filters.regex(r"^([Yy][Oo][Uu][Tt][Uu][Bb][Ee][Pp][Ll][Aa][Yy])") | filters.regex(r"^(پخش یوتیوب)")))
async def youtube_play(client, m: Message):
    uid = m.from_user.id
    horn = [*database.kir(1), *database.kir(0)]
    if uid not in utils.video_access(m.chat.id, uid):
        return
    if m.chat.id not in horn:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if await utils.checkjoin(client, m, uid) is not None:
        return
    if m.chat.id not in database.insvideo():
        return
    if not await require_helper(uid, m):
        return
    text = utils.clean_command(utils.msg_text(m), "پخش یوتیوب", "YoutubePlay").strip()
    if not utils.is_youtube_link(text):
        return await m.reply(
            i18n.t(
                uid,
                "لینک وارد شده معتبر نیست !\nلینک باید به یکی از صورت‌های زیر باشد :\n"
                "`https://www.youtube.com/watch?v=...`\n`https://youtu.be/...`",
                "The link is invalid !\nThe link must look like one of :\n"
                "`https://www.youtube.com/watch?v=...`\n`https://youtu.be/...`",
            )
        )
    status = await m.reply(
        i18n.t(uid, "**⌯** در حال دانلود از یوتیوب ... **⌯**",
               "**⌯** Downloading from YouTube ... **⌯**")
    )
    try:
        info = await utils.ytdlp_info(text)
        title = (info or {}).get("title") or "YouTube"
        path, why = await utils.ytdlp_download(
            text, f"ytv_{m.chat.id}_{uid}_{m.id}", video=True
        )
        if not path:
            await _del(status)
            return await m.reply(_download_failed(uid, why))
        await _del(status)
        resolution, duration = await utils.probe_media(path)
        print("Playing {} in {}".format(path, m.chat.title))
        await play_video(client, m, path, title, resolution=resolution, duration=duration)
    except Exception as exc:
        print(exc)
        await _del(status)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))


# ----------------------------------------------------------------------
# Playlist: افزودن به لیست / پخش لیست / توقف لیست / لیست پخش / حذف از لیست / پاکسازی
# ----------------------------------------------------------------------
@app.on_message(filters.group & filters.reply & (filters.regex(r"^(افزودن به لیست)$") | filters.regex(r"^([Aa][Dd][Dd][Tt][Oo][Pp][Ll][Aa][Yy][Ll][Ii][Ss][Tt])$")))
async def add_to_playlist(client, m: Message):
    uid = m.from_user.id
    if uid not in utils.music_access(m.chat.id, uid):
        return
    if m.chat.id not in database.insmusic():
        return
    if not (m.reply_to_message and m.reply_to_message.audio):
        return
    audio = m.reply_to_message.audio
    rows = database.query("SELECT path FROM playlist WHERE idgp=?", (m.chat.id,))
    if len(rows) >= 10:
        return await m.reply(i18n.t(uid, "**⌯** شما نمیتوانید بیشتر از 10 موزیک به لیست پخش اضافه کنید **!**", "**⌯** You cannot add more than 10 songs to the playlist **!**"))
    safe_title = "".join(ch for ch in (audio.title or "song") if ch not in '/\\:*?"<>|')
    folder = os.path.join(cfg.DOWNLOAD_DIR, str(m.chat.id))
    os.makedirs(folder, exist_ok=True)
    path = await m.reply_to_message.download(file_name=os.path.join(folder, f"{safe_title}.mp3"))
    existing = [r[0] for r in rows]
    if path in existing:
        return await m.reply(i18n.t(uid, "**⌯** موزیک در لیست پخش وجود دارد **!**", "**⌯** The song is already in the playlist **!**"))
    database.execute("INSERT INTO playlist(idgp, path, duration) VALUES(?,?,?)", (m.chat.id, path, audio.duration or 60))
    await m.reply(i18n.t(uid, f"**⌯** موزیک **{audio.title}** به لیست پخش اضافه شد **!**", f"**⌯** Song **{audio.title}** added to the playlist **!**"))


@app.on_message(filters.group & filters.reply & (filters.regex(r"^(حذف از لیست)$") | filters.regex(r"^([Dd][Ee][Ll][Ff][Rr][Oo][Mm][Pp][Ll][Aa][Yy][Ll][Ii][Ss][Tt])$")))
async def remove_from_playlist(client, m: Message):
    uid = m.from_user.id
    if uid not in utils.music_access(m.chat.id, uid):
        return
    if m.chat.id not in database.insmusic():
        return
    audio = m.reply_to_message.audio if m.reply_to_message else None
    if audio is None:
        return
    safe_title = "".join(ch for ch in (audio.title or "song") if ch not in '/\\:*?"<>|')
    folder = os.path.join(cfg.DOWNLOAD_DIR, str(m.chat.id))
    path = os.path.join(folder, f"{safe_title}.mp3")
    if database.query("SELECT path FROM playlist WHERE path=?", (path,)) == []:
        return await m.reply(i18n.t(uid, "• موزیک مورد نظر در لیست پخش موجود نیست !", "• The song is not in the playlist !"))
    database.execute("DELETE FROM playlist WHERE path=?", (path,))
    await m.reply(i18n.t(uid, "• موزیک مورد نظر با موفقیت از لیست پخش حذف شد !", "• The song was removed from the playlist !"))


@app.on_message(filters.group & (filters.regex(r"^(لیست پخش)$") | filters.regex(r"^([Ll][Ii][Ss][Tt][Pp][Ll][Aa][Yy][Ll][Ii][Ss][Tt])$")))
async def show_playlist(client, m: Message):
    uid = m.from_user.id
    if uid not in utils.music_access(m.chat.id, uid):
        return
    if m.chat.id not in database.insmusic():
        return
    rows = database.query("SELECT path FROM playlist WHERE idgp=?", (m.chat.id,))
    if rows == []:
        return await m.reply(i18n.t(uid, "• لیست خالی میباشد !", "• The list is empty !"))
    char = ""
    counter = 1
    for r in rows:
        name = os.path.basename(r[0]).replace(".mp3", "")
        char += f"{counter} - {name}\n─┅━━━━━━━━✥━━━━━━━━┅─\n"
        counter += 1
    await m.reply(char)


@app.on_message(filters.group & (filters.regex(r"^(پاکسازی لیست پخش)$") | filters.regex(r"^([Cc][Ll][Ee][Aa][Nn][Pp][Ll][Aa][Yy][Ll][Ii][Ss][Tt])$")))
async def clear_playlist(client, m: Message):
    uid = m.from_user.id
    if uid not in utils.music_access(m.chat.id, uid):
        return
    if m.chat.id not in database.insmusic():
        return
    if database.query("SELECT path FROM playlist WHERE idgp=?", (m.chat.id,)) == []:
        return await m.reply(i18n.t(uid, "**⌯** لیست پخش خالی میباشد **!**", "**⌯** The playlist is empty **!**"))
    database.execute("DELETE FROM playlist WHERE idgp=?", (m.chat.id,))
    await m.reply(i18n.t(uid, "**⌯** لیست پخش پاکسازی شد **!**", "**⌯** The playlist was cleaned **!**"))


async def _playlist_runner(client, m, rows):
    """Sequentially play all playlist tracks as a background task.

    /skip sets SKIP_EVENT[chat_id], which advances to the next track.
    """
    chat_id = m.chat.id
    try:
        for row in rows:
            if PLAYLIS.get(chat_id) != "running":
                break
            path = row[0]
            duration = row[2] or 60
            try:
                await call_py.join_group_call(chat_id, AudioPiped(path))
            except Exception:
                # skip unplayable track and keep going
                continue
            ev = SKIP_EVENT.setdefault(chat_id, asyncio.Event())
            try:
                await asyncio.wait_for(ev.wait(), timeout=max(duration - 1, 1))
            except asyncio.TimeoutError:
                pass
            except asyncio.CancelledError:
                break
            if ev.is_set():
                ev.clear()
            try:
                await call_py.leave_group_call(chat_id)
            except Exception:
                pass
    except asyncio.CancelledError:
        pass
    finally:
        PLAYLIS.pop(chat_id, None)
        PLAYLIST_TASKS.pop(chat_id, None)
        SKIP_EVENT.pop(chat_id, None)
        try:
            await call_py.leave_group_call(chat_id)
        except Exception:
            pass


@app.on_message(filters.group & (filters.regex(r"^(پخش لیست)$") | filters.regex(r"^([Pp][Ll][Aa][Yy][Ll][Ii][Ss][Tt])$")))
async def play_playlist(client, m: Message):
    uid = m.from_user.id
    if uid not in utils.music_access(m.chat.id, uid):
        return
    if m.chat.id not in database.insmusic():
        return
    if not await require_helper(uid, m):
        return
    rows = database.query("SELECT * FROM playlist WHERE idgp=?", (m.chat.id,))
    if rows == []:
        return await m.reply(i18n.t(uid, "**⌯** لیست پخش خالی میباشد **!**", "**⌯** The playlist is empty **!**"))
    # cancel any running playlist task
    old_task = PLAYLIST_TASKS.pop(m.chat.id, None)
    if old_task:
        old_task.cancel()
    PLAYLIS[m.chat.id] = "running"
    try:
        await call_py.leave_group_call(m.chat.id)
    except Exception:
        pass
    a = utils.jalali_now()
    fa = (
        f"**⌯** **لیست پخش در حال پخش میباشد** **🔊**\n"
        f"**⊹** نام درخواست کننده : {m.from_user.mention(m.from_user.first_name)}\n"
        f"**⊹** شناسه گروه : `{m.chat.id}`\n"
        f"**⊹** `وضعیت : درحال پخش`\n"
        f"**⊹** ساعت : `{a}` 🕦"
    )
    en = (
        f"**⌯** **Playlist is playing** **🔊**\n"
        f"**⊹** Requested by : {m.from_user.mention(m.from_user.first_name)}\n"
        f"**⊹** Group id : `{m.chat.id}`\n"
        f"**⊹** `Status : playing`\n"
        f"**⊹** Time : `{a}` 🕦"
    )
    await utils.send_card(
        client, m.chat.id, uid, fa, en,
        reply_markup=utils.player_keyboard(uid, "playlist"),
        reply_to_message_id=m.id,
    )
    PLAYLIST_TASKS[m.chat.id] = asyncio.create_task(_playlist_runner(client, m, rows))


@app.on_message(filters.group & (filters.regex(r"^(توقف لیست)$") | filters.regex(r"^([Ss][Tt][Oo][Pp][Ll][Ii][Ss][Tt])$")))
async def stop_playlist(client, m: Message):
    uid = m.from_user.id
    if uid not in utils.music_access(m.chat.id, uid):
        return
    if m.chat.id not in database.insmusic():
        return
    rows = database.query("SELECT path FROM playlist WHERE idgp=?", (m.chat.id,))
    if rows == []:
        return await m.reply(i18n.t(uid, "**⌯** لیست پخش خالی میباشد **!**", "**⌯** The playlist is empty **!**"))
    task = PLAYLIST_TASKS.pop(m.chat.id, None)
    if task:
        task.cancel()
    PLAYLIS.pop(m.chat.id, None)
    try:
        await call_py.leave_group_call(m.chat.id)
    except Exception:
        pass
    a = utils.jalali_now()
    fa = (
        f"**⌯** **لیست پخش متوقف شد** **🔇**\n"
        f"**⊹** نام درخواست کننده : {m.from_user.mention(m.from_user.first_name)}\n"
        f"**⊹** شناسه گروه : `{m.chat.id}`\n"
        f"**⊹** ساعت : `{a}` 📅"
    )
    en = (
        f"**⌯** **Playlist stopped** **🔇**\n"
        f"**⊹** Requested by : {m.from_user.mention(m.from_user.first_name)}\n"
        f"**⊹** Group id : `{m.chat.id}`\n"
        f"**⊹** Time : `{a}` 📅"
    )
    await utils.send_card(client, m.chat.id, uid, fa, en, reply_to_message_id=m.id)


# ======================================================================
# Slash-command aliases: /play /pause /resume /stop /skip /playvideo
# /stopvideo /playlist /stoplist /playfile  (plus Persian equivalents)
# ======================================================================
@app.on_message(filters.group & filters.command(["play", "p"]))
async def slash_play(client, m: Message):
    """/play <reply-audio> | /play <url> | /play <username|id>"""
    uid = m.from_user.id
    horn = [*database.moz(1), *database.moz(0)]
    access = utils.music_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    if m.chat.id not in database.insmusic():
        return
    if not await require_helper(uid, m):
        return

    parts = (m.text or "").split(None, 1)
    arg = parts[1].strip().lstrip("@") if len(parts) > 1 else ""

    # 1) reply to an audio/voice
    if m.reply_to_message and (m.reply_to_message.audio or m.reply_to_message.voice):
        if await utils.checkjoin(client, m, uid) is not None:
            return
        status = await m.reply(
            i18n.t(uid, "**⌯** در حال دانلود ... **⌯**", "**⌯** Downloading ... **⌯**")
        )
        path = await _download_media(client, m.reply_to_message, uid, "mus", status)
        if not path:
            return await m.reply(
                i18n.t(uid, "• دانلود فایل با مشکل مواجه شد !", "• Failed to download the file !")
            )
        dur = None
        if m.reply_to_message.audio and m.reply_to_message.audio.duration:
            dur = m.reply_to_message.audio.duration
        elif m.reply_to_message.voice and m.reply_to_message.voice.duration:
            dur = m.reply_to_message.voice.duration
        print("Playing {} in {}".format(path, m.chat.title))
        try:
            await play_audio(client, m, path, media_name(m.reply_to_message), duration=dur)
        except Exception as exc:
            print(exc)
            await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))
        return

    # 2) direct URL
    if arg.startswith("http"):
        if await utils.checkjoin(client, m, uid) is not None:
            return
        status = await m.reply(i18n.t(uid, "**⌯** در حال دریافت ... **⌯**", "**⌯** Fetching ... **⌯**"))
        try:
            # a YouTube link handed straight to ffmpeg failed outright -
            # ffmpeg has no YouTube demuxer, so it has to be resolved first.
            path, title, _resolution, err = await _resolve_stream_url(arg, m.chat.id, uid, m.id, False)
            if not path:
                await _del(status)
                return await m.reply(_download_failed(uid, err))
            await _del(status)
            print("Playing {} in {}".format(path, m.chat.title))
            await play_audio(client, m, path, title)
        except Exception as exc:
            print(exc)
            await _del(status)
            await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))
        return

    # 3) dedicate to a user
    if arg:
        if await utils.checkjoin(client, m, uid) is not None:
            return
        if not (m.reply_to_message and (m.reply_to_message.audio or m.reply_to_message.voice)):
            return await m.reply(
                i18n.t(uid, "• لطفا به یک موزیک ریپلای کنید !", "• Please reply to an audio first !")
            )
        target = await utils.resolve_chat(arg)
        if target is None:
            return await m.reply(i18n.t(uid, "• کاربر مورد نظر یافت نشد !", "• The requested user was not found !"))
        status = await m.reply(
            i18n.t(uid, "**⌯** در حال دانلود ... **⌯**", "**⌯** Downloading ... **⌯**")
        )
        path = await _download_media(client, m.reply_to_message, uid, "ded", status)
        if not path:
            return await m.reply(
                i18n.t(uid, "• دانلود فایل با مشکل مواجه شد !", "• Failed to download the file !")
            )
        dur = None
        if m.reply_to_message.audio and m.reply_to_message.audio.duration:
            dur = m.reply_to_message.audio.duration
        try:
            await play_dedicated_music(client, m, path, target, media_name(m.reply_to_message), duration=dur)
        except Exception as exc:
            print(exc)
            await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))
        return

    await m.reply(
        i18n.t(
            uid,
            "• فرمت :\n`/play` (ریپلای به موزیک)\n`/play لینک`\n`/play یوزرنیم`",
            "• Usage :\n`/play` (reply to an audio)\n`/play <url>`\n`/play <username>`",
        )
    )


@app.on_message(filters.group & filters.command(["playvideo", "pv"]))
async def slash_playvideo(client, m: Message):
    """/playvideo <reply-video> | <url> | <username>"""
    uid = m.from_user.id
    horn = [*database.kir(1), *database.kir(0)]
    access = utils.video_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    if m.chat.id not in database.insvideo():
        return
    if not await require_helper(uid, m):
        return

    parts = (m.text or "").split(None, 1)
    arg = parts[1].strip().lstrip("@") if len(parts) > 1 else ""

    if m.reply_to_message and m.reply_to_message.video:
        if await utils.checkjoin(client, m, uid) is not None:
            return
        try:
            video = m.reply_to_message.video
            resolution = [video.width, video.height]
            path = await app.download_media(m.reply_to_message, file_name=os.path.join(cfg.DOWNLOAD_DIR, f"vid_{m.chat.id}_{uid}_{m.id}.mp4"))
            print("Playing {} in {}".format(path, m.chat.title))
            await play_video(client, m, path, "—", resolution=resolution, reply_id=m.reply_to_message.id)
        except Exception as exc:
            print(exc)
            await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))
        return

    if arg.startswith("http"):
        if await utils.checkjoin(client, m, uid) is not None:
            return
        status = await m.reply(i18n.t(uid, "**⌯** در حال دریافت ... **⌯**", "**⌯** Fetching ... **⌯**"))
        try:
            path, title, resolution, err = await _resolve_stream_url(arg, m.chat.id, uid, m.id, True)
            if not path:
                await _del(status)
                return await m.reply(_download_failed(uid, err))
            await _del(status)
            print("Playing {} in {}".format(path, m.chat.title))
            await play_video(client, m, path, title, resolution=resolution)
        except Exception as exc:
            print(exc)
            await _del(status)
            await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))
        return

    if arg:
        if await utils.checkjoin(client, m, uid) is not None:
            return
        if not (m.reply_to_message and m.reply_to_message.video):
            return await m.reply(
                i18n.t(uid, "• لطفا به یک ویدیو ریپلای کنید !", "• Please reply to a video first !")
            )
        target = await utils.resolve_chat(arg)
        if target is None:
            return await m.reply(i18n.t(uid, "• کاربر مورد نظر یافت نشد !", "• The requested user was not found !"))
        try:
            video = m.reply_to_message.video
            resolution = [video.width, video.height]
            path = await app.download_media(m.reply_to_message, file_name=os.path.join(cfg.DOWNLOAD_DIR, f"dvid_{m.chat.id}_{uid}_{m.id}.mp4"))
            await play_dedicated_video(client, m, path, target, resolution)
        except Exception as exc:
            print(exc)
            await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))
        return

    await m.reply(
        i18n.t(
            uid,
            "• فرمت :\n`/playvideo` (ریپلای به ویدیو)\n`/playvideo لینک`\n`/playvideo یوزرنیم`",
            "• Usage :\n`/playvideo` (reply to a video)\n`/playvideo <url>`\n`/playvideo <username>`",
        )
    )


@app.on_message(filters.group & filters.command(["pause"]))
async def slash_pause(client, m: Message):
    await pause_cmd(client, m)


@app.on_message(filters.group & filters.command(["resume", "continue"]))
async def slash_resume(client, m: Message):
    await resume_cmd(client, m)


@app.on_message(filters.group & filters.command(["stop"]))
async def slash_stop(client, m: Message):
    """/stop - stops music or video (or the playlist)."""
    if m.chat.id in PLAYLIS:
        await stop_playlist(client, m)
        return
    if m.chat.id in PLAYING:
        kind = (utils.STREAMS.get(m.chat.id) or {}).get("kind")
        if kind == "video":
            await stopvideo(client, m)
        else:
            await stopmusic(client, m)
        return
    uid = m.from_user.id
    await m.reply(i18n.t(uid, "• چیزی در حال پخش نیست !", "• Nothing is playing !"))


@app.on_message(filters.group & filters.command(["stopmusic"]))
async def slash_stopmusic(client, m: Message):
    await stopmusic(client, m)


@app.on_message(filters.group & filters.command(["stopvideo"]))
async def slash_stopvideo(client, m: Message):
    await stopvideo(client, m)


@app.on_message(filters.group & filters.command(["skip", "next"]))
async def slash_skip(client, m: Message):
    """/skip - skip the current track (playlist) or stop the current stream."""
    uid = m.from_user.id
    access = [*database.allmusic(), *database.allvideo(), *database.idsudos(), *database.idowner(),
              *database.creators(m.chat.id), *database.idmusic(m.chat.id), *database.idvideo(m.chat.id),
              SUDO, OWNER]
    if uid not in access:
        return

    # playlist running -> advance to the next track
    if m.chat.id in PLAYLIS and PLAYLIS.get(m.chat.id) == "running":
        ev = SKIP_EVENT.setdefault(m.chat.id, asyncio.Event())
        ev.set()
        await m.reply(i18n.t(uid, "**⌯** به موزیک بعدی رفتیم **!**", "**⌯** Skipped to the next track **!**"))
        return

    # single stream -> stop it
    if m.chat.id in PLAYING:
        await stopmusic(client, m)
        return

    await m.reply(i18n.t(uid, "• چیزی در حال پخش نیست !", "• Nothing is playing !"))


@app.on_message(filters.group & filters.command(["playlist", "pl"]))
async def slash_playlist(client, m: Message):
    await play_playlist(client, m)


@app.on_message(filters.group & filters.command(["stoplist"]))
async def slash_stoplist(client, m: Message):
    await stop_playlist(client, m)


@app.on_message(filters.group & filters.command(["playfile", "pf"]))
async def slash_playfile(client, m: Message):
    parts = (m.text or "").split(None, 1)
    arg = parts[1].strip() if len(parts) > 1 else ""
    if not arg:
        uid = m.from_user.id
        return await m.reply(
            i18n.t(
                uid,
                "• فرمت : `/playfile مسیر/فایل.mp3`",
                "• Usage : `/playfile /path/to/file.mp3`",
            )
        )
    await _play_local_file(client, m, arg)


@app.on_message(filters.group & (filters.regex(r"^(پخش فایل )") | filters.regex(r"^([Pp][Ll][Aa][Yy][Ff][Ii][Ll][Ee]) ")))
async def play_file_cmd(client, m: Message):
    uid = m.from_user.id
    arg = utils.clean_command(m.text, "پخش فایل", "PlayFile").strip()
    if not arg:
        return await m.reply(
            i18n.t(
                uid,
                "• فرمت : `پخش فایل مسیر/فایل.mp3`",
                "• Usage : `PlayFile /path/to/file.mp3`",
            )
        )
    await _play_local_file(client, m, arg)


def _resolve_local_media(path: str):
    """Resolve a user-supplied path and confine it to DOWNLOAD_DIR.

    `_play_local_file` used to accept any path on the host, so `PlayFile
    /etc/passwd` (or `../../`) streamed an arbitrary server file into the
    voice chat. Returns the safe absolute path, or None if it escapes.
    """
    root = os.path.realpath(cfg.DOWNLOAD_DIR)
    candidate = path if os.path.isabs(path) else os.path.join(root, path)
    target = os.path.realpath(candidate)
    if target != root and not target.startswith(root + os.sep):
        return None
    return target


async def _play_local_file(client, m: Message, path: str):
    """Play a local file - audio or video is auto-detected by extension."""
    uid = m.from_user.id
    safe = _resolve_local_media(path)
    if safe is None:
        return await m.reply(
            i18n.t(
                uid,
                "• این مسیر مجاز نیست **!** فقط فایل های داخل پوشه ی `downloads` قابل پخش هستند.",
                "• That path is not allowed **!** Only files inside the `downloads` folder can be played.",
            )
        )
    path = safe
    if not os.path.isfile(path):
        return await m.reply(
            i18n.t(uid, "• فایل در مسیر مشخص شده یافت نشد !", "• The file was not found at the given path !")
        )
    if not await require_helper(uid, m):
        return

    is_audio = utils.is_audio_path(path)
    if is_audio:
        horn = [*database.moz(1), *database.moz(0)]
        access = utils.music_access(m.chat.id, uid)
        if m.chat.id not in horn and uid in access:
            return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
        if uid not in access:
            return
        if m.chat.id not in database.insmusic():
            return
        if await utils.checkjoin(client, m, uid) is not None:
            return
        resolution, duration = await utils.probe_media(path)
        try:
            print("Playing {} in {}".format(path, m.chat.title))
            await play_audio(client, m, path, os.path.basename(path), duration=duration)
        except Exception as exc:
            print(exc)
            await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))
        return

    # video
    horn = [*database.kir(1), *database.kir(0)]
    access = utils.video_access(m.chat.id, uid)
    if m.chat.id not in horn and uid in access:
        return await m.reply(i18n.t(uid, "• گروه فاقد اعتبار میباشد !", "• The group has no credit !"))
    if uid not in access:
        return
    if m.chat.id not in database.insvideo():
        return
    if await utils.checkjoin(client, m, uid) is not None:
        return
    try:
        resolution, duration = await utils.probe_media(path)
        print("Playing {} in {}".format(path, m.chat.title))
        await play_video(client, m, path, os.path.basename(path), resolution=resolution, duration=duration)
    except Exception as exc:
        print(exc)
        await m.reply(i18n.t(uid, "• پخش با مشکل مواجه شد !", "• Playback failed !"))
