"""
MusicRasool - shared utilities.

- access control (sudos / owners / music & video admins / creators)
- "now playing" media cards (photo -> video -> text fallback)
- player control keyboards (exact original layout, bilingual labels)
- YouTube direct-URL extraction (yt-dlp) and Melobit search API
- Jalali (Persian) timestamp helper
"""
import asyncio
import logging
import os
import re
import subprocess
import time

import jdatetime
from pyrogram import enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import config
import database
import i18n
from clients import app, ubot

logger = logging.getLogger("musicrasool")

cfg = config.get_config()

PLAYING = {}   # chat_id -> path/url currently playing
PLAYLIS = {}   # chat_id -> playlist progress
STREAMS = {}   # chat_id -> stream metadata (see mark_streaming)

import itertools as _itertools

_GEN = _itertools.count(1)


def mark_streaming(chat_id, kind, path, resolution=None, duration=None,
                   retries=None, fails=None):
    """Register an intentionally-playing stream (survives for reconnect).

    - gen: increases on every (re)start, so stale stream-end events from a
      previous stream can be detected/ignored.
    - ignore_until: a grace window after a join during which stream-end
      events are ignored (they are almost always the *previous* stream
      being stopped by our own leave_group_call).
    """
    entry = {
        "kind": kind,
        "path": path,
        "resolution": resolution,
        "duration": duration,
        "gen": next(_GEN),
        "fails": fails if fails is not None else 0,
        "retries": retries if retries is not None else 0,
        "started_at": time.time(),
        "ignore_until": time.time() + 6,
    }
    STREAMS[chat_id] = entry
    PLAYING[chat_id] = path
    return entry


def clear_streaming(chat_id):
    """Remove an intentionally-playing stream (no auto-reconnect)."""
    old = PLAYING.pop(chat_id, None)
    STREAMS.pop(chat_id, None)
    return old


def build_stream(entry):
    """Build the pytgcalls stream object for a STREAMS entry (lazy import)."""
    from pytgcalls.types.raw import VideoParameters
    from pytgcalls.types.stream.legacy import AudioPiped, AudioVideoPiped

    if entry["kind"] == "audio":
        return AudioPiped(entry["path"])
    if entry.get("resolution"):
        return AudioVideoPiped(
            entry["path"],
            video_parameters=VideoParameters(*entry["resolution"]),
        )
    return AudioVideoPiped(entry["path"])


async def join_with_retry(chat_id, stream, tries=2, delay=1.0):
    """join_group_call with a couple of transient-failure retries."""
    from clients import call_py

    last = None
    for i in range(tries):
        try:
            await call_py.join_group_call(chat_id, stream)
            return True
        except Exception as exc:  # noqa: BLE001
            last = exc
            if i < tries - 1:
                await asyncio.sleep(delay)
    if last is not None:
        raise last
    return False


async def rejoin_stream(chat_id, entry):
    """Leave (best effort) then re-join the stream described by `entry`."""
    from clients import call_py

    try:
        await call_py.leave_group_call(chat_id)
    except Exception:
        pass
    await join_with_retry(chat_id, build_stream(entry), tries=2)

# ----------------------------------------------------------------------
# Access control (identical semantics to the original bot)
# ----------------------------------------------------------------------
def owners_ids():
    return [cfg.OWNER_ID, cfg.SUDO_ID, *database.idsudos(), *database.idowner()]


def music_access(chat_id, user_id=None):
    return [*database.idsudos(), *database.idowner(), *database.idmusic(chat_id),
            *database.creators(chat_id), cfg.SUDO_ID, cfg.OWNER_ID, *database.allmusic()]


def video_access(chat_id, user_id=None):
    return [*database.idsudos(), *database.idowner(), *database.idvideo(chat_id),
            *database.creators(chat_id), cfg.SUDO_ID, cfg.OWNER_ID, *database.allvideo()]


def panel_access(chat_id):
    return [*database.idsudos(), *database.idowner(), cfg.OWNER_ID, cfg.SUDO_ID,
            *database.creators(chat_id)]


def sudo_access():
    return [*database.idsudos(), *database.idowner(), cfg.OWNER_ID, cfg.SUDO_ID]


# ----------------------------------------------------------------------
# Timestamps
# ----------------------------------------------------------------------
def jalali_now(lang: str = "fa") -> str:
    """`HH:MM:SS` + the current Jalali date.

    The Jalali calendar was formatted with the *default* (English) locale, so
    Persian users saw "Sat 14 Sha 1405". The date is now rendered with Persian
    weekday/month names unless `lang == "en"`.
    """
    try:
        now = jdatetime.datetime.now()
        if str(lang).lower().startswith("en"):
            dat = now.strftime("\n%a %d %b %Y")
        else:
            dat = now.aslocale(jdatetime.FA_LOCALE).strftime("\n%a %d %b %Y")
        return now.strftime("%H:%M:%S") + dat
    except Exception:
        return time.strftime("%H:%M:%S\n%a %d %b %Y")


# ----------------------------------------------------------------------
# Media cards
# ----------------------------------------------------------------------
async def send_card(client, chat_id, user_id, fa_text, en_text=None,
                    reply_markup=None, reply_to_message_id=None,
                    parse_mode=enums.ParseMode.MARKDOWN):
    """Send a 'now playing' card. Photo -> video -> plain text fallback."""
    text = i18n.t(user_id, fa_text, en_text)
    photo = os.path.join(cfg.ASSETS_DIR, "mersad.jpg")
    video = os.path.join(cfg.ASSETS_DIR, "mersad.mp4")
    for kind in ("photo", "video", "text"):
        try:
            if kind == "photo":
                await client.send_photo(
                    chat_id, photo, caption=text, reply_markup=reply_markup,
                    reply_to_message_id=reply_to_message_id, parse_mode=parse_mode,
                )
            elif kind == "video":
                await client.send_video(
                    chat_id, video, caption=text, reply_markup=reply_markup,
                    reply_to_message_id=reply_to_message_id, parse_mode=parse_mode,
                    supports_streaming=True,
                )
            else:
                await client.send_message(
                    chat_id, text, reply_markup=reply_markup,
                    reply_to_message_id=reply_to_message_id, parse_mode=parse_mode,
                )
            return
        except Exception as exc:
            if kind == "text":
                # last resort: no parse mode at all
                try:
                    await client.send_message(
                        chat_id, text, reply_markup=reply_markup,
                        reply_to_message_id=reply_to_message_id,
                    )
                except Exception as exc2:
                    logger.warning("send_card failed completely: %s %s", exc, exc2)
            else:
                logger.debug("send_card %s failed: %s", kind, exc)


# ----------------------------------------------------------------------
# Player keyboards (EXACT original layout, bilingual labels)
# ----------------------------------------------------------------------
def player_keyboard(user_id, kind="music"):
    """kind: 'music' | 'video' | 'playlist'"""
    if kind == "music":
        pause, stop, resume = "pausee", "closee", "resumee"
        mute, unmute, close = "mutemus", "unmutemus", "cls"
    elif kind == "video":
        pause, stop, resume = "pauseeee", "closeeee", "resumeeee"
        mute, unmute, close = "mutevid", "unmutevid", "clls"
    else:  # playlist
        pause, stop, resume = "pauseee", "closeee", "resumeee"
        mute, unmute, close = "mutemus", "unmutemus", "cls"

    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(user_id, "• در حال پخش", "• Now Playing"), callback_data="a")],
            [
                InlineKeyboardButton(i18n.t(user_id, "⏸ مکث", "⏸ Pause"), callback_data=pause),
                InlineKeyboardButton(i18n.t(user_id, "⏹ توقف", "⏹ Stop"), callback_data=stop),
                InlineKeyboardButton(i18n.t(user_id, "▶️ ازسرگیری", "▶️ Resume"), callback_data=resume),
            ],
            [
                InlineKeyboardButton(i18n.t(user_id, "🔇 بیصدا", "🔇 Mute"), callback_data=mute),
                InlineKeyboardButton(i18n.t(user_id, "🔊 باصدا", "🔊 Unmute"), callback_data=unmute),
            ],
            [InlineKeyboardButton(i18n.t(user_id, "• بستن", "• Close"), callback_data=close)],
        ]
    )


def install_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(user_id, "• نصب ویدیو", "• Install Video"), callback_data="installvideo"),
             InlineKeyboardButton(i18n.t(user_id, "• نصب موزیک", "• Install Music"), callback_data="installmusic")],
            [InlineKeyboardButton(i18n.t(user_id, "• پیکربندی", "• Configure"), callback_data="config")],
            [InlineKeyboardButton(i18n.t(user_id, "• تنظیم شارژ", "• Set Charge"), callback_data="charge"),
             InlineKeyboardButton(i18n.t(user_id, "• افزودن هلپر", "• Add Helper"), callback_data="addcli")],
            [InlineKeyboardButton(i18n.t(user_id, "• بستن پنل", "• Close Panel"), callback_data="closepannel")],
        ]
    )


def delete_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(user_id, "• حذف موزیک", "• Delete Music"), callback_data="delmus"),
             InlineKeyboardButton(i18n.t(user_id, "• حذف ویدیو", "• Delete Video"), callback_data="delvid")],
            [InlineKeyboardButton(i18n.t(user_id, "• حذف کلی", "• Delete All"), callback_data="delboth")],
            [InlineKeyboardButton(i18n.t(user_id, "• خروج ربات", "• Leave Group"), callback_data="left")],
            [InlineKeyboardButton(i18n.t(user_id, "• بستن پنل", "• Close Panel"), callback_data="closedel")],
        ]
    )


def charge_menu_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(user_id, "• شارژ ویدیو", "• Charge Video"), callback_data="chargevideo"),
             InlineKeyboardButton(i18n.t(user_id, "• شارژ موزیک", "• Charge Music"), callback_data="chargemusic")],
            [InlineKeyboardButton(i18n.t(user_id, "• بازگشت", "• Back"), callback_data="back1")],
            [InlineKeyboardButton(i18n.t(user_id, "• بستن پنل", "• Close Panel"), callback_data="closepannel")],
        ]
    )


def months_keyboard(user_id, kind="1"):
    """kind '1' -> video (mah1), kind '2' -> music (mah2)"""
    suffix = "1" if kind == "1" else "2"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(user_id, "• 1 ماه", "• 1 Month"), callback_data=f"1mah{suffix}"),
             InlineKeyboardButton(i18n.t(user_id, "• 2 ماه", "• 2 Months"), callback_data=f"2mah{suffix}")],
            [InlineKeyboardButton(i18n.t(user_id, "• 3 ماه", "• 3 Months"), callback_data=f"3mah{suffix}"),
             InlineKeyboardButton(i18n.t(user_id, "• 4 ماه", "• 4 Months"), callback_data=f"4mah{suffix}")],
            [InlineKeyboardButton(i18n.t(user_id, "• بازگشت", "• Back"), callback_data="back2")],
        ]
    )


def tv_menu_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("• ماهواره", callback_data="mahvare"),
             InlineKeyboardButton("• تلویزیون", callback_data="telev")],
            [InlineKeyboardButton(i18n.t(user_id, "• بستن پنل", "• Close Panel"), callback_data="closetv")],
        ]
    )


def tv_ir_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("• شبکه 2", callback_data="tv2"), InlineKeyboardButton("• شبکه 1", callback_data="tv1")],
            [InlineKeyboardButton("• شبکه 5", callback_data="tv5"), InlineKeyboardButton("• شبکه 3", callback_data="tv3")],
            [InlineKeyboardButton("• شبکه آی‌فیلم", callback_data="ifilm"), InlineKeyboardButton("• شبکه خبر", callback_data="news")],
            [InlineKeyboardButton("• شبکه نمایش", callback_data="namayesh"), InlineKeyboardButton("• شبکه نسیم", callback_data="nasim")],
            [InlineKeyboardButton("• شبکه تماشا", callback_data="hdtest"), InlineKeyboardButton("• شبکه ورزش", callback_data="varzesh")],
            [InlineKeyboardButton(i18n.t(user_id, "• بستن پنل", "• Close Panel"), callback_data="closetv"),
             InlineKeyboardButton(i18n.t(user_id, "• بازگشت", "• Back"), callback_data="backahura")],
        ]
    )


def tv_sat_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("• BBC", callback_data="bbc"), InlineKeyboardButton("• ManotoTv", callback_data="manoto")],
            [InlineKeyboardButton("• AvaFamily", callback_data="avafamily"), InlineKeyboardButton("• AvaSeries", callback_data="avaseries")],
            [InlineKeyboardButton("• FarsiTv", callback_data="farsitv"), InlineKeyboardButton("• PMC", callback_data="pmc")],
            [InlineKeyboardButton("• Vox 2", callback_data="vox2"), InlineKeyboardButton("• Vox 1", callback_data="vox1")],
            [InlineKeyboardButton("• NavahangMusic", callback_data="navahang"), InlineKeyboardButton("• RadioJavan", callback_data="radiojavan")],
            [InlineKeyboardButton("• IranInternational", callback_data="iraninternational"), InlineKeyboardButton("• ITN", callback_data="itn")],
            [InlineKeyboardButton("• GemTv", callback_data="gemtv"), InlineKeyboardButton("• OxirTv", callback_data="owirtv")],
            [InlineKeyboardButton("• GemRubix", callback_data="gemrubix"), InlineKeyboardButton("• GemRiver", callback_data="gemriver")],
            [InlineKeyboardButton("• GemBollywood", callback_data="gembollywood"), InlineKeyboardButton("• GemSeries", callback_data="gemseries")],
            [InlineKeyboardButton("• GemJunior", callback_data="gemjunior"), InlineKeyboardButton("• GemDrama", callback_data="gemdrama")],
            [InlineKeyboardButton("• GemFilm", callback_data="gemfilm"), InlineKeyboardButton("• GemMaxx", callback_data="gemmaxx")],
            [InlineKeyboardButton("• BBC Persian", callback_data="bbcpersian"), InlineKeyboardButton("• MBC Persia", callback_data="mbcpersia")],
            [InlineKeyboardButton("• Tapesh 1", callback_data="tapesh1"), InlineKeyboardButton("• Tapesh 2", callback_data="tapesh2")],
            [InlineKeyboardButton("• PersianaTv", callback_data="persiana"), InlineKeyboardButton("• PMC Royale", callback_data="pmcr")],
            [InlineKeyboardButton(i18n.t(user_id, "• بستن پنل", "• Close Panel"), callback_data="closetv"),
             InlineKeyboardButton(i18n.t(user_id, "• بازگشت", "• Back"), callback_data="backahura")],
        ]
    )


def help_keyboard(user_id):
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(user_id, "• سرچ و پخش خودکار", "• Search & Autoplay"), callback_data="helpvideo")],
            [InlineKeyboardButton(i18n.t(user_id, "• ارتقا و عزل", "• Promote & Demote"), callback_data="helpmusic")],
            [InlineKeyboardButton(i18n.t(user_id, "• پخش ها", "• Playback"), callback_data="inlinefun"),
             InlineKeyboardButton(i18n.t(user_id, "• کاربردی", "• Utilities"), callback_data="karbordi")],
            [InlineKeyboardButton(i18n.t(user_id, "• تیوی و لیست پخش", "• TV & Playlist"), callback_data="inlinemanage")],
            [InlineKeyboardButton(i18n.t(user_id, "• بستن", "• Close"), callback_data="closehelp")],
        ]
    )


def back_help_keyboard(user_id):
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.t(user_id, "• بازگشت", "• Back"), callback_data="backhelp")]]
    )


def start_keyboard(user_id, info, channel_link):
    kirsag = channel_link or "https://t.me/fnvhfdmnfhjkc"
    groupp = info.get("groupp") or "+NFHJK4757FDSDF"
    adminpv = info.get("adminpv") or "bdchvjndchvj"
    payamresan = info.get("payamresan") or "dbgchjnebdh"
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(i18n.t(user_id, "📚 اطلاعات بیشتر", "📚 More Info"), callback_data="aboutus")],
            [InlineKeyboardButton(i18n.t(user_id, "💻 خرید مستقیم از سازنده", "💻 Direct Purchase"), url=f"https://t.me/{adminpv}")],
            [InlineKeyboardButton(i18n.t(user_id, "▪️ کانال ربات", "▪️ Bot Channel"), url=kirsag),
             InlineKeyboardButton(i18n.t(user_id, "▪️ گروه پشتیبانی", "▪️ Support Group"), url=f"https://t.me/{groupp}")],
            [InlineKeyboardButton(i18n.t(user_id, "📮 خرید غیر مستقیم", "📮 Indirect Purchase"), url=f"https://t.me/{payamresan}")],
        ]
    )


# ----------------------------------------------------------------------
# YouTube direct URL (yt-dlp, falls back to youtube-dl)
# ----------------------------------------------------------------------
async def utub(link: str) -> str:
    """Return a direct streamable URL for a YouTube link (best <=720p)."""
    for exe in ("yt-dlp", "youtube-dl"):
        try:
            proc = await asyncio.create_subprocess_exec(
                exe, "-g", "-f", "best[height<=?720][width<=?1280]", link,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            out = stdout.decode(errors="ignore").split("\n")[0].strip()
            if out:
                return out
        except FileNotFoundError:
            continue
    return ""


async def probe_resolution(path: str):
    """Return [width, height] of a local video via ffprobe, or None."""
    for exe in ("ffprobe",):
        try:
            proc = await asyncio.create_subprocess_exec(
                exe, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height",
                "-of", "csv=s=x:p=0", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            out = stdout.decode(errors="ignore").strip()
            if out and "x" in out:
                w, h = out.split("x")[:2]
                return [int(w), int(h)]
        except FileNotFoundError:
            continue
        except Exception:
            pass
    return None


async def probe_duration(path: str):
    """Return the media duration in seconds via ffprobe, or None."""
    for exe in ("ffprobe",):
        try:
            proc = await asyncio.create_subprocess_exec(
                exe, "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
            out = stdout.decode(errors="ignore").strip()
            if out:
                try:
                    return float(out)
                except ValueError:
                    return None
        except FileNotFoundError:
            continue
        except Exception:
            pass
    return None


async def probe_media(path: str):
    """Return (resolution, duration) of a local media file."""
    resolution = await probe_resolution(path)
    duration = await probe_duration(path)
    return resolution, duration


def is_audio_path(path: str) -> bool:
    ext = os.path.splitext(str(path).split("?")[0])[1].lower()
    return ext in (".mp3", ".m4a", ".aac", ".ogg", ".opus", ".wav", ".flac", ".wma", ".webm_audio")


def is_youtube_link(text: str) -> bool:
    return "youtube.com/watch" in text or "youtu.be/" in text


# ----------------------------------------------------------------------
# Melobit search (used by "search" and "autoplay" commands)
# ----------------------------------------------------------------------
async def melobit_search(query: str, limit: int = 1):
    """Return list of song dicts from Melobit public API."""
    import aiohttp
    base = cfg.MELOBIT_API.rstrip("/")
    url = f"{base}/search/song?query={query}&limit={limit}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    return []
                data = await resp.json()
        return data.get("results", [])
    except Exception as exc:
        logger.warning("melobit search failed: %s", exc)
        return []


async def fetch_media(url: str, name: str, max_bytes: int = 300 * 1024 * 1024):
    """Download a media URL into DOWNLOAD_DIR and return its path (or None).

    Telegram only lets a bot upload-by-URL files up to 20 MB, so handing a
    remote URL to `send_audio` fails for anything longer than a few minutes.
    Fetching the bytes ourselves and uploading the local file removes that
    ceiling (bots may upload up to 50 MB) and keeps the failure visible.
    """
    import aiohttp

    cfg = config.get_config()
    os.makedirs(cfg.DOWNLOAD_DIR, exist_ok=True)
    safe_name = "".join(ch for ch in (name or "media") if ch not in '/\\:*?"<>|') or "media"
    dest = os.path.join(cfg.DOWNLOAD_DIR, safe_name)
    try:
        timeout = aiohttp.ClientTimeout(total=180)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as resp:
                if resp.status != 200:
                    return None
                total = 0
                with open(dest, "wb") as fh:
                    async for chunk in resp.content.iter_chunked(128 * 1024):
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValueError("file too large")
                        fh.write(chunk)
        return dest
    except Exception as exc:
        logging.getLogger(__name__).warning("fetch_media failed for %s: %s", url, exc)
        try:
            os.remove(dest)
        except OSError:
            pass
        return None


async def melobit_song(song_id):
    import aiohttp
    base = cfg.MELOBIT_API.rstrip("/")
    url = f"{base}/song/{song_id}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=20) as resp:
                if resp.status != 200:
                    return None
                return await resp.json()
    except Exception as exc:
        logger.warning("melobit song failed: %s", exc)
        return None


def melobit_download_url(music_info):
    """Return best quality mp3 direct URL from a Melobit song payload."""
    audio = (music_info.get("audio") or {}).get("high") or {}
    medium = (music_info.get("audio") or {}).get("medium") or {}
    return audio.get("url") or medium.get("url") or ""


def melobit_cover(music_info):
    image = music_info.get("image") or {}
    cover = image.get("cover") or {}
    return cover.get("url") or ""


def melobit_title(music_info):
    song = music_info.get("song") or music_info
    return song.get("title") or "Unknown"


# ----------------------------------------------------------------------
# Chat / user resolvers (via helper userbot, fallback to bot)
# ----------------------------------------------------------------------
async def resolve_chat(query):
    """Resolve @username or numeric id to a Chat."""
    query = str(query).strip()
    try:
        if query.lstrip("-").isdigit():
            return await ubot.get_chat(int(query))
        return await ubot.get_chat(query)
    except Exception:
        try:
            if query.lstrip("-").isdigit():
                return await app.get_chat(int(query))
            return await app.get_chat(query)
        except Exception:
            return None


def is_number(text: str) -> bool:
    return bool(re.fullmatch(r"-?\d+", str(text).strip()))


def brief_error(exc) -> str:
    """Short, safe one-liner for user-facing error messages.

    A raw `str(exc)` from Pyrogram embeds the Telegram error description and,
    for local failures, file paths and internals. Show the class name (plus
    the stable Telegram error id when there is one) and keep the detail in
    the log.
    """
    name = type(exc).__name__
    err_id = getattr(exc, "ID", None)
    return f"{name} ({err_id})" if err_id else name


def msg_text(m) -> str:
    """The text a `filters.regex` handler actually matched.

    `filters.regex` matches `message.text or message.caption`, so a photo or
    video with a matching caption reaches these handlers with
    `m.text is None` - touching it directly raised AttributeError and the
    command silently did nothing.
    """
    return getattr(m, "text", None) or getattr(m, "caption", None) or ""


def clean_command(text: str, fa_prefix: str, en_prefix: str) -> str:
    """Strip a command prefix (Persian or English) from message text."""
    text = "" if text is None else str(text)
    text = text.replace(fa_prefix, "")
    m = re.search(re.escape(en_prefix) + r"\b", text, flags=re.IGNORECASE)
    if m:
        text = text.replace(m.group(0), "")
    return text.strip()


# ----------------------------------------------------------------------
# Force-join (channel) check - same behavior as the original bot
# ----------------------------------------------------------------------
async def checkjoin(client, m, user_id):
    """Returns None if the user may proceed, otherwise a string code."""
    from pyrogram.errors import ChatAdminRequired, ChannelInvalid, UserNotParticipant

    list_moaf = [r[1] for r in database.query("SELECT idgp, idadmin FROM ejbar WHERE idgp=?", (m.chat.id,))]
    if user_id in list_moaf:
        return None

    ch_rows = database.channel()
    if ch_rows == []:
        return None
    x = ch_rows[0]
    # channel columns: 0=idchannel 1=namechannel 2=invite 3=status
    # `status` is written by the owner panel (join_on / join_off); without this
    # check force-join could never be switched off again.
    if len(x) < 4 or not x[3]:
        return None
    uid = user_id
    fa_join = "◂ کاربر عزیز {mention} برای دستور دادن به ربات ابتدا باید در کانال ربات عضو شوید."
    fa_admin = "• لطفا ابتدا ربات را در کانال زیر ادمین کرده و سپس مجددا تلاش کنید !"
    fa_generic = "• کاربر عزیز {mention} لطفا ابتدا در کانال زیر عضو شوید و سپس مجددا تلاش کنید !"

    markup_chan = InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.t(uid, "▪️ کانال ما", "▪️ Our Channel"), url=x[2])]]
    )
    markup_admin = InlineKeyboardMarkup(
        [[InlineKeyboardButton(i18n.t(uid, "▪️ کانال ربات", "▪️ Bot Channel"), url=x[2])]]
    )
    try:
        await client.get_chat_member(x[0], user_id)
        return None
    except UserNotParticipant:
        mention = m.from_user.mention(m.from_user.first_name) if m.from_user else str(user_id)
        await m.reply(i18n.t(uid, fa_join.format(mention=mention), fa_join.format(mention=mention).replace("کاربر عزیز", "Dear user")), reply_markup=markup_chan)
        return "kos"
    except (ChatAdminRequired, ChannelInvalid):
        await m.reply(i18n.t(uid, fa_admin, "• Please make the bot an admin of the channel below and try again !"), reply_markup=markup_admin)
        return "kir"
    except Exception:
        mention = m.from_user.mention(m.from_user.first_name) if m.from_user else str(user_id)
        await m.reply(i18n.t(uid, fa_generic.format(mention=mention), fa_generic.format(mention=mention).replace("کاربر عزیز", "Dear user")), reply_markup=markup_chan)
        return "kos"
