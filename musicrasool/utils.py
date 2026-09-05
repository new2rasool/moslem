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
import shutil
import sys
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
    """Every user id allowed to run music commands in `chat_id`.

    `user_id` is accepted but deliberately unused: the lists below already
    contain every per-chat and global music role, so the requester's own id
    adds nothing. It is kept so the 22 existing `music_access(chat_id, uid)`
    call sites stay valid.
    """
    return [*database.idsudos(), *database.idowner(), *database.idmusic(chat_id),
            *database.creators(chat_id), cfg.SUDO_ID, cfg.OWNER_ID, *database.allmusic()]


def video_access(chat_id, user_id=None):
    """Same as `music_access` for video commands; `user_id` is unused (see above)."""
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
# ----------------------------------------------------------------------
# External binaries and YouTube (yt-dlp) helpers
# ----------------------------------------------------------------------
# `best[...]` alone asks yt-dlp for a single combined (video+audio) format,
# which YouTube only serves up to 720p and not for every video - the old
# selector therefore returned nothing for a large share of links and the
# caller could only report a generic "download failed". These chains fall
# back to separate video+audio (merged by ffmpeg) and then to anything.
YTDLP_FMT_VIDEO = (
    "bv*[height<=?720][ext=mp4]+ba[ext=m4a]/"
    "bv*[height<=?720]+ba/"
    "b[height<=?720]/"
    "bv*+ba/b"
)
YTDLP_FMT_AUDIO = "ba[ext=m4a]/ba[ext=mp3]/ba/b"


def _find_exe(*names):
    """Locate a binary on PATH, then next to the running interpreter.

    `yt-dlp` is installed into the virtualenv, so it is only on PATH when the
    venv is activated (what run.sh/run.bat do). Looking next to
    sys.executable keeps it working when the bot is started any other way.
    """
    for n in names:
        found = shutil.which(n)
        if found:
            return found
    bindir = os.path.dirname(os.path.abspath(sys.executable))
    for n in names:
        for cand in (os.path.join(bindir, n), os.path.join(bindir, n + ".exe")):
            if os.path.isfile(cand) and os.access(cand, os.X_OK):
                return cand
    return None


def ytdlp_exe():
    """Path to the yt-dlp CLI, or None when it is not installed."""
    return _find_exe("yt-dlp", "youtube-dl")


def ffmpeg_missing() -> bool:
    """True when no ffmpeg can be found (streaming cannot work at all)."""
    if _find_exe("ffmpeg"):
        return False
    try:
        import imageio_ffmpeg
        return not os.path.exists(imageio_ffmpeg.get_ffmpeg_exe())
    except Exception:
        return True


async def _run_cmd(cmd, timeout=600):
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        await proc.communicate()
        raise
    return proc.returncode, out.decode(errors="ignore"), err.decode(errors="ignore")


def _safe_name(text: str, default: str = "media") -> str:
    cleaned = "".join(ch for ch in (text or "") if ch not in '/\\:*?"<>|').strip()
    return (cleaned[:80] or default)


async def ytdlp_info(url: str):
    """Metadata for a URL via yt-dlp, or None."""
    exe = ytdlp_exe()
    if not exe:
        return None
    try:
        rc, out, _err = await _run_cmd(
            [exe, "--no-playlist", "--dump-single-json", "--no-warnings", url],
            timeout=120,
        )
    except Exception as exc:
        logger.warning("yt-dlp info failed for %s: %s", url, exc)
        return None
    if rc != 0 or not out.strip():
        return None
    import json
    try:
        return json.loads(out)
    except Exception:
        return None


async def ytdlp_search(query: str, limit: int = 1):
    """Search YouTube. Returns a list of {"title", "url"} dicts.

    yt-dlp's own search is used first because it is maintained together with
    the extractor; `youtube-search-python` scrapes the HTML page and breaks
    whenever YouTube changes markup, so it is only a fallback.
    """
    exe = ytdlp_exe()
    if exe:
        try:
            rc, out, _err = await _run_cmd(
                [exe, f"ytsearch{limit}:{query}", "--dump-single-json",
                 "--no-warnings", "--flat-playlist"],
                timeout=120,
            )
            if rc == 0 and out.strip():
                import json
                data = json.loads(out)
                entries = data.get("entries") or []
                found = []
                for e in entries:
                    url = e.get("url") or e.get("webpage_url")
                    vid = e.get("id")
                    if not url and vid:
                        url = f"https://www.youtube.com/watch?v={vid}"
                    if url:
                        found.append({"title": e.get("title") or "YouTube", "url": url})
                if found:
                    return found
        except Exception as exc:
            logger.warning("yt-dlp search failed: %s", exc)

    # fallback: youtube-search-python
    try:
        from youtubesearchpython import VideosSearch

        def _blocking():
            return VideosSearch(query, limit=limit).result().get("result") or []

        rows = await asyncio.to_thread(_blocking)
        return [{"title": r.get("title") or "YouTube", "url": r["link"]}
                for r in rows if r.get("link")]
    except Exception as exc:
        logger.warning("youtube-search-python failed: %s", exc)
        return []


# Upper bound for a file fetched from an arbitrary link. Telegram media goes
# through fetch_media() and is capped by Telegram itself, but a plain URL has
# no natural limit and would otherwise fill the disk.
MAX_LINK_BYTES = 300 * 1024 * 1024


async def download_url(url: str, prefix: str, suffix: str = ""):
    """Stream a plain HTTP(S) file into DOWNLOAD_DIR.

    Returns (path, None) on success or (None, reason) on failure. Downloading
    instead of handing the URL to ffmpeg means we can probe the real
    resolution before streaming (the legacy VideoParameters() call hard-coded
    640x360 for every link) and gives a readable error on failure.
    """
    import aiohttp
    cfg = config.get_config()
    os.makedirs(cfg.DOWNLOAD_DIR, exist_ok=True)
    if not suffix:
        suffix = os.path.splitext(url.split("?")[0])[1][:8] or ".bin"
    dest = os.path.join(cfg.DOWNLOAD_DIR, f"{_safe_name(prefix, 'link')}{suffix}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=300) as resp:
                if resp.status != 200:
                    return None, f"HTTP {resp.status}"
                total = 0
                with open(dest, "wb") as fh:
                    async for chunk in resp.content.iter_chunked(1 << 16):
                        total += len(chunk)
                        if total > MAX_LINK_BYTES:
                            fh.close()
                            os.remove(dest)
                            return None, f"file is larger than {MAX_LINK_BYTES // (1 << 20)} MB"
                        fh.write(chunk)
    except Exception as exc:
        try:
            if os.path.exists(dest):
                os.remove(dest)
        except Exception:
            pass
        return None, brief_error(exc)
    if not os.path.exists(dest) or os.path.getsize(dest) == 0:
        return None, "the download was empty"
    return dest, None


async def ytdlp_download(url: str, prefix: str, video: bool = True):
    """Download a URL into DOWNLOAD_DIR and return (path, title) or (None, why).

    Streaming the remote URL straight into ffmpeg used to fail for YouTube
    (the direct googlevideo URL expires, needs the right format and sometimes
    headers). Downloading first is what the Melobit music path already does
    and it also lets us probe the real resolution.
    """
    exe = ytdlp_exe()
    if not exe:
        return None, "yt-dlp is not installed (pip install -r requirements.txt)"
    if ffmpeg_missing():
        return None, "ffmpeg is missing - streaming cannot work"

    cfg = config.get_config()
    os.makedirs(cfg.DOWNLOAD_DIR, exist_ok=True)
    template = os.path.join(cfg.DOWNLOAD_DIR, f"{_safe_name(prefix, 'yt')}.%(ext)s")
    fmt = YTDLP_FMT_VIDEO if video else YTDLP_FMT_AUDIO
    cmd = [exe, "-f", fmt, "--no-playlist", "--no-warnings",
           "--restrict-filenames", "--no-overwrites", "-o", template, url]
    if video:
        cmd += ["--merge-output-format", "mp4"]
    try:
        rc, _out, err = await _run_cmd(cmd, timeout=900)
    except asyncio.TimeoutError:
        return None, "yt-dlp timed out"
    except Exception as exc:
        return None, f"yt-dlp failed: {brief_error(exc)}"
    if rc != 0:
        # last non-empty stderr line is the human-readable reason
        lines = [ln.strip() for ln in err.splitlines() if ln.strip()]
        return None, (lines[-1][:200] if lines else f"yt-dlp exited with {rc}")

    stem = os.path.join(cfg.DOWNLOAD_DIR, _safe_name(prefix, "yt"))
    for ext in ("mp4", "m4a", "webm", "mkv", "mp3", "opus", "m4v"):
        cand = f"{stem}.{ext}"
        if os.path.isfile(cand) and os.path.getsize(cand) > 0:
            return cand, ""
    # --restrict-filenames may have altered the stem; fall back to a scan
    newest, newest_ts = None, 0.0
    for fn in os.listdir(cfg.DOWNLOAD_DIR):
        fp = os.path.join(cfg.DOWNLOAD_DIR, fn)
        if os.path.isfile(fp) and os.path.getmtime(fp) > newest_ts:
            newest, newest_ts = fp, os.path.getmtime(fp)
    if newest:
        return newest, ""
    return None, "yt-dlp produced no file"


async def utub(link: str) -> str:
    """Return a direct streamable URL for a YouTube link (<=720p).

    Kept for compatibility, but prefer `ytdlp_download()`: the direct URL
    expires and cannot be probed for resolution.
    """
    exe = ytdlp_exe()
    if not exe:
        return ""
    try:
        rc, out, err = await _run_cmd(
            [exe, "-g", "-f", YTDLP_FMT_VIDEO, "--no-playlist", "--no-warnings", link],
            timeout=180,
        )
    except Exception as exc:
        logger.warning("utub failed for %s: %s", link, exc)
        return ""
    if rc != 0:
        logger.warning("utub: %s", (err or "").strip().splitlines()[-1:] or rc)
        return ""
    # -g prints one URL per stream (video then audio); the first is the video
    return out.split("\n")[0].strip()


def ffmpeg_exe():
    """Path to an ffmpeg binary: PATH, next to the interpreter, or imageio-ffmpeg.

    `imageio-ffmpeg` ships a static ffmpeg but **no ffprobe**, which is why the
    ffprobe-only probes below need an ffmpeg fallback.
    """
    found = _find_exe("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg
        cand = imageio_ffmpeg.get_ffmpeg_exe()
        if cand and os.path.exists(cand):
            return cand
    except Exception:
        pass
    return None


async def _ffmpeg_banner(path: str):
    """Run `ffmpeg -i <path>` and return its stderr banner (it exits non-zero)."""
    exe = ffmpeg_exe()
    if not exe:
        return ""
    try:
        proc = await asyncio.create_subprocess_exec(
            exe, "-hide_banner", "-i", path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _out, err = await asyncio.wait_for(proc.communicate(), 60)
    except Exception:
        return ""
    return err.decode(errors="ignore")


def stream_resolution(url: str):
    """Best-effort [width, height] for a live-stream URL, or None.

    A livestream cannot be downloaded and probed first, so the resolution is
    read from the URL (`.../720p/index.m3u8`). Without this, `AudioVideoPiped`
    fell back to the legacy VideoParameters() default and every 720p channel
    was downscaled to 640x360.
    """
    m = re.search(r"(\d{3,4})p", str(url or "").lower())
    if not m:
        return None
    h = int(m.group(1))
    if not 144 <= h <= 4320:
        return None
    return [int(round(h * 16 / 9 / 2.0)) * 2, h]


async def probe_resolution(path: str):
    """Return [width, height] of a video, or None.

    Both probes used to call a hard-coded `ffprobe` and swallow
    FileNotFoundError, so on any machine without ffprobe on PATH they silently
    returned None: every video was streamed at the legacy 640x360 default and
    the early-end detector had no duration to work with. ffprobe is now looked
    up properly and ffmpeg's banner is used as a fallback.
    """
    exe = _find_exe("ffprobe")
    if exe:
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
        except Exception as exc:
            logger.debug("ffprobe failed for %s: %s", path, exc)
    # fallback: `Video: h264 ..., 1280x720 [...]` in the ffmpeg banner
    banner = await _ffmpeg_banner(path)
    for line in banner.splitlines():
        if "Video:" in line:
            m = re.search(r"(\d{2,5})x(\d{2,5})", line)
            if m:
                return [int(m.group(1)), int(m.group(2))]
    return None


async def probe_duration(path: str):
    """Return the media duration in seconds, or None.

    See probe_resolution: the hard-coded `ffprobe` call silently returned None
    on machines without it, which made the early-end detector treat a normally
    long song as a failure.
    """
    exe = _find_exe("ffprobe")
    if exe:
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
                    pass
        except Exception as exc:
            logger.debug("ffprobe duration failed for %s: %s", path, exc)
    # fallback: `Duration: 00:00:07.31,` in the ffmpeg banner. Live streams
    # report `Duration: N/A`, which correctly stays None.
    banner = await _ffmpeg_banner(path)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", banner)
    if m:
        h, mi, sec = m.groups()
        return int(h) * 3600 + int(mi) * 60 + float(sec)
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
    """True for the YouTube URL shapes users actually paste.

    The old check only accepted `youtube.com/watch`, so `youtu.be/...`,
    `/shorts/...`, `/live/...` and `music.youtube.com` links were rejected
    as "invalid link".
    """
    t = (text or "").lower()
    return ("youtube.com/" in t or "youtu.be/" in t or "youtube-nocookie.com/" in t)


# ----------------------------------------------------------------------
# Melobit search (used by "search" and "autoplay" commands)
# ----------------------------------------------------------------------
async def melobit_search(query: str, limit: int = 1):
    """Return list of song dicts from Melobit public API."""
    import aiohttp
    base = cfg.MELOBIT_API.rstrip("/")
    # the query was interpolated straight into the URL, so a song title with
    # "#" truncated it into a fragment and "&" split it into extra params.
    url = f"{base}/search/song"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params={"query": query, "limit": limit},
                                   timeout=20) as resp:
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
