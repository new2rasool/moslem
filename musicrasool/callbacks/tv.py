"""
TV channel callbacks (پخش تیوی): Iranian national channels and
satellite (mahvare) channels. All channels/URLs preserved from the
original bot.
"""
from pyrogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

import config
import database
import i18n
import utils
from clients import call_py, helper_ready
from pytgcalls.types.stream.legacy import AudioVideoPiped

cfg = config.get_config()
OWNER = cfg.OWNER_ID
SUDO = cfg.SUDO_ID

# channel callback_data -> (name, stream URL)
CHANNELS = {
    # --- Iranian national TV (telev) ---
    "tv1": ("شبکه یک", "https://cdn.telewebion.com/tv1/live/720p/index.m3u8"),
    "tv2": ("شبکه دو", "https://cdn.telewebion.com/tv2/live/720p/index.m3u8"),
    "tv3": ("شبکه سه", "https://cdn.telewebion.com/tv3/live/720p/index.m3u8"),
    "tv5": ("شبکه پنج", "https://cdn.telewebion.com/tehran/live/720p/index.m3u8"),
    "news": ("شبکه خبر", "https://cdn.telewebion.com/irinn/live/720p/index.m3u8"),
    "ifilm": ("شبکه آی‌فیلم", "https://cdn.telewebion.com/ifilm/live/720p/index.m3u8"),
    "namayesh": ("شبکه نمایش", "https://cdn.telewebion.com/namayesh/live/720p/index.m3u8"),
    "nasim": ("شبکه نسیم", "https://cdn.telewebion.com/nasim/live/720p/index.m3u8"),
    "hdtest": ("شبکه تماشا", "https://cdn.telewebion.com/hdtest/live/720p/index.m3u8"),
    "varzesh": ("شبکه ورزش", "https://cdn.telewebion.com/varzesh/live/720p/index.m3u8"),
    # --- Satellite (mahvare) ---
    "bbc": ("BBC", "https://vs-hls-pushb-ww-live.akamaized.net/x=3/i=urn:bbc:pips:service:bbc_persian_tv/t=3840/v=pv5/b=437056/main.m3u8"),
    "bbcpersian": ("BBC Persian", "https://vs-hls-pushb-ww-live.akamaized.net/x=3/i=urn:bbc:pips:service:bbc_persian_tv/pc_hd_abr_v2_akamai_hls_live.m3u8"),
    "manoto": ("ManotoTv", "https://d2rwmwucnr0d10.cloudfront.net/live_750.m3u8"),
    "avafamily": ("AvaFamily", "http://51.210.199.5/hls/stream.m3u8"),
    "avaseries": ("AvaSeries", "http://51.210.199.4/hls/stream.m3u8"),
    "farsitv": ("FarsiTv", "https://live.farsitv.de/live/stream_720p/index.m3u8"),
    "pmc": ("PMC", "https://hls.pmchd.live/hls/stream.m3u8"),
    "pmcr": ("PMC Royale", "http://51.210.199.29/hls/stream.m3u8"),
    "vox1": ("Vox 1", "http://51.210.199.8/hls/stream.m3u8"),
    "vox2": ("Vox 2", "http://51.210.199.9/hls/stream.m3u8"),
    "navahang": ("NavahangMusic", "http://51.210.227.130/hls/stream.m3u8"),
    "radiojavan": ("RadioJavan", "https://stream.rjtv.stream/live/smil:rjtv.smil/playlist.m3u8"),
    "iraninternational": ("IranInternational", "https://live.playstop.me/1816184091/index.m3u8"),
    "itn": ("ITN", "https://livestream.5centscdn.com/itnapp/4e0ea63032b868402b61d3a35e7ca168.sdp/chunks.m3u8"),
    "gemtv": ("GemTv", "https://stream-live.gemonline.tv/live/gem/index.m3u8"),
    "owirtv": ("OxirTv", "http://51.254.225.26/hls/stream.m3u8"),
    "gemrubix": ("GemRubix", "https://stream-live.gemonline.tv/live/rubix/index.m3u8"),
    "gemriver": ("GemRiver", "https://stream-live.gemonline.tv/live/river/index.m3u8"),
    "gembollywood": ("GemBollywood", "https://stream-live.gemonline.tv/live/gembollywood/index.m3u8"),
    "gemseries": ("GemSeries", "https://stream-live.gemonline.tv/live/gemseries/index.m3u8"),
    "gemjunior": ("GemJunior", "https://stream-live.gemonline.tv/live/gemjunior/index.m3u8"),
    "gemdrama": ("GemDrama", "https://stream-live.gemonline.tv/live/gemdrama/index.m3u8"),
    "gemfilm": ("GemFilm", "https://stream-live.gemonline.tv/live/gemfilm/index.m3u8"),
    "gemmaxx": ("GemMaxx", "https://stream-live.gemonline.tv/live/gemmaxx/index.m3u8"),
    "mbcpersia": ("MBC Persia", "https://shls-mbcpersia-prod-dub.shahid.net/out/v1/bdc7cd0d990e4c54808632a52c396946/index.m3u8"),
    "tapesh1": ("Tapesh 1", "http://iptv.tapesh.tv/tapesh/playlist.m3u8"),
    "tapesh2": ("Tapesh 2", "http://208.113.204.104:8123/live/tapesh-live-stream/index.m3u8"),
    "persiana": ("PersianaTv", "http://51.210.199.22/hls/stream.m3u8"),
}


# keys of the national (telev) list - everything else in CHANNELS is satellite
NATIONAL = {"tv1", "tv2", "tv3", "tv5", "news", "ifilm", "namayesh", "nasim", "hdtest", "varzesh"}


def _tv_access(chat_id):
    return [*database.idsudos(), *database.idowner(), OWNER, SUDO, *database.creators(chat_id),
            *database.idvideo(chat_id), *database.allvideo()]


async def handle_tv(client, m: CallbackQuery, data: str):
    uid = m.from_user.id
    chat_id = m.message.chat.id

    if data == "telev":
        await m.edit_message_text(
            i18n.t(uid, "• جهت پخش، یکی از شبکه های زیر را انتخاب کنید :", "• Choose a channel to play :"),
            reply_markup=utils.tv_ir_keyboard(uid),
        )
        return True

    if data == "mahvare":
        await m.edit_message_text(
            i18n.t(uid, "• جهت پخش، یکی از شبکه های زیر را انتخاب کنید :", "• Choose a channel to play :"),
            reply_markup=utils.tv_sat_keyboard(uid),
        )
        return True

    if data == "closetv":
        await m.answer(i18n.t(uid, "• پنل بسته شد !", "• Panel closed !"), show_alert=True)
        try:
            await m.message.delete()
        except Exception:
            pass
        return True

    if data == "backtv":
        # back to the telev (national) list
        # Edit the message in place: deleting it first and then replying to it
        # fails with "message to reply not found", so the panel just vanished.
        await m.edit_message_text(
            i18n.t(uid, "• جهت پخش، یکی از شبکه های زیر را انتخاب کنید :", "• Choose a channel to play :"),
            reply_markup=utils.tv_ir_keyboard(uid),
        )
        return True

    if data == "backahura":
        await m.edit_message_text(
            i18n.t(uid, "• لطفا یکی از گزینه های زیر را انتخاب کنید :", "• Please choose one of the options below :"),
            reply_markup=utils.tv_menu_keyboard(uid),
        )
        return True

    if data == "backma":
        await m.edit_message_text(
            i18n.t(uid, "• جهت پخش، یکی از شبکه های زیر را انتخاب کنید :", "• Choose a channel to play :"),
            reply_markup=utils.tv_sat_keyboard(uid),
        )
        return True

    if data in CHANNELS:
        name, path = CHANNELS[data]
        if not helper_ready():
            await m.answer(i18n.t(uid, "• حساب هلپر وارد نشده است !", "• The helper account is not logged in !"), show_alert=True)
            return True
        try:
            await call_py.leave_group_call(chat_id)
        except Exception:
            pass
        try:
            print("Playing {} in {}".format(path, m.message.chat.title))
            await call_py.join_group_call(chat_id, AudioVideoPiped(path))
            utils.mark_streaming(chat_id, "video", path)
        except Exception as exc:
            print(exc)
            await m.answer(i18n.t(uid, "• پخش شبکه با مشکل مواجه شد !", "• Failed to start the channel !"), show_alert=True)
            return True
        a = utils.jalali_now()
        fa = (
            f"**⌯ {name} در حال پخش میباشد 🔊**\n"
            f"**⊹** نام درخواست کننده : {m.from_user.mention(m.from_user.first_name)}\n"
            f"**⊹** ساعت : `{a}` 📅"
        )
        en = (
            f"**⌯ {name} is now playing 🔊**\n"
            f"**⊹** Requested by : {m.from_user.mention(m.from_user.first_name)}\n"
            f"**⊹** Time : `{a}` 📅"
        )
        try:
            await m.message.delete()
        except Exception:
            pass
        await utils.send_card(
            client, chat_id, uid, fa, en,
            reply_markup=InlineKeyboardMarkup(
                [
                    # `backtv` returns to the national list, `backma` to the
                    # satellite list. The button used to be hard-coded to
                    # `backtv`, so leaving a satellite channel dropped the
                    # user into the wrong panel (and `backma` was dead code).
                    [InlineKeyboardButton(
                        i18n.t(uid, "• بازگشت", "• Back"),
                        callback_data="backtv" if data in NATIONAL else "backma"),
                     InlineKeyboardButton(i18n.t(uid, "• توقف", "• Stop"), callback_data="closee")],
                ]
            ),
        )
        return True

    return False
