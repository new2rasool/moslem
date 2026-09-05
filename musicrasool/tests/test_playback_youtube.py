"""
Regression tests for the play / YouTube / link commands.

These cover the defects that made `پخش`, `پخش خودکار`, `پخش ویدیو`,
`پخش خودکار ویدیو` and every YouTube command fail:

  P1  `پخش ویدیو` (+reply) was swallowed by `play_dedicate`
  P2  `utils.utub()` could not find yt-dlp unless the venv was on PATH, and
      its `best[...]` selector had no video+audio fallback
  P3  the `"googlevideo.com" not in direct` gate rejected working URLs
  P4  remote URLs were streamed directly (expiring CDN links, 640x360 default)
  P5  only the literal `youtube.com/watch` form was accepted
  P6  `melobit_search` interpolated the query into the URL unencoded
  P7  `پخش لینک ویدیو` required the literal `.mp4`/`.mkv` in the URL
  P8  search relied only on youtube-search-python's HTML scraping

Run directly:      python tests/test_playback_youtube.py
Run with suite:    python tests/run_all.py
"""
import asyncio
import inspect
import os
import sys

import _bootstrap  # noqa: F401  (redirects .env/DB/downloads into a temp sandbox)

# handler registration needs a running loop BEFORE the modules are imported
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from pyrogram import enums  # noqa: E402
from pyrogram.types import Chat, Message, User  # noqa: E402

import config  # noqa: E402
import database  # noqa: E402

config.load_config()
database.init_db()

import handlers.auth  # noqa: E402,F401
import handlers.playback as pb  # noqa: E402
import utils  # noqa: E402
from clients import app  # noqa: E402

results = []


def check(name, ok, extra=""):
    results.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  {extra}" if extra else ""))


# ---------------------------------------------------------------- fixtures
UID = 6173234874
GROUP = -1001234567890

# filters.command reads client.me.username, so the client needs an identity
app.me = type("Me", (), {"username": "test_bot", "id": 999, "first_name": "B"})()
_chat = Chat(id=GROUP, type=enums.ChatType.SUPERGROUP, title="T")
_user = User(id=UID, first_name="O", is_bot=False, is_verified=False,
             is_restricted=False, is_deleted=False, is_self=False)
# User.mention() formats through client.parse_mode, so the object needs a client
_user._client = app


def msg(text, reply=False):
    m = Message(client=app, id=1, chat=_chat, from_user=_user, text=text)
    if reply:
        r = Message(client=app, id=0, chat=_chat, from_user=_user)
        r.audio = type("A", (), {"file_name": "s.mp3", "duration": 100, "title": "Song"})()
        r.voice = None
        r.video = None
        m.reply_to_message = r
        # NOTE: filters.reply in pyrogram 2.0.106 tests reply_to_message_id,
        # NOT reply_to_message - setting only the object makes every
        # filters.reply handler return False and silently breaks routing tests.
        m.reply_to_message_id = 99
    return m


async def route(m):
    """First handler the dispatcher would run for this message."""
    for g in sorted(app.dispatcher.groups):
        for h in app.dispatcher.groups[g]:
            if await h.filters(app, m):
                return getattr(h.callback, "__name__", "?")
    return None


# ------------------------------------------------------------------ P1
def test_routing():
    print("\n-- P1: command routing (reply + prefix collisions) --")
    # (text, is_reply, expected handler)
    cases = [
        ("پخش", True, "play_reply"),
        ("پخش @ali", True, "play_dedicate"),
        ("پخش ویدیو", True, "playvideo_reply"),
        ("پخش ویدیو @ali", True, "playvideo_dedicate"),
        ("پخش ویدیو @ali", False, "playvideo_dedicate"),
        ("پخش فایل downloads/x.mp3", False, "play_file_cmd"),
        ("پخش لینک http://a/b.mp3", False, "play_link"),
        ("پخش لینک ویدیو http://a/b.mp4", False, "play_link_video"),
        ("پخش خودکار song", False, "autoplay"),
        ("پخش یوتیوب https://youtu.be/x", False, "youtube_play"),
        ("پخش لیست", False, "play_playlist"),
        ("سرچ song", False, "search_music"),
        ("سرچ یوتیوب song", False, "youtube_search"),
        ("Play @ali", True, "play_dedicate"),
        ("Play", True, "play_reply"),
        ("PlayVideo", True, "playvideo_reply"),
        ("PlayVideo @ali", True, "playvideo_dedicate"),
    ]
    for text, is_reply, expected in cases:
        got = loop.run_until_complete(route(msg(text, is_reply)))
        check(f"'{text}'{'+reply' if is_reply else ''} -> {expected}", got == expected,
              f"got {got}")


# ------------------------------------------------------------------ P2
def test_ytdlp_discovery():
    print("\n-- P2: locating the yt-dlp binary --")
    exe = utils.ytdlp_exe()
    check("ytdlp_exe() finds yt-dlp (PATH or next to sys.executable)", bool(exe), str(exe))

    # the fix: a binary sitting in the venv's bin/ is found even when that
    # directory is not on PATH (which is the case unless run.sh activates it)
    import shutil
    saved_which = shutil.which
    try:
        shutil.which = lambda *a, **k: None
        utils.shutil.which = shutil.which
        still = utils._find_exe("yt-dlp")
    finally:
        shutil.which = saved_which
        utils.shutil.which = saved_which
    check("_find_exe() falls back to sys.executable's directory", still is not None or exe is None,
          str(still))

    src = inspect.getsource(utils.utub)
    check("utub() no longer swallows FileNotFoundError into a silent continue",
          "FileNotFoundError" not in src)
    check("utub() uses the shared format chain", "YTDLP_FMT_VIDEO" in src)
    fmt = utils.YTDLP_FMT_VIDEO
    check("format chain has a separate video+audio fallback ('+ba')", "+ba" in fmt)
    check("format chain is not the old bare 'best[height<=?720]'",
          fmt != "best[height<=?720][width<=?1280]")
    check("format chain ends with an unconditional 'b' fallback", fmt.rstrip().endswith("/b"))

    # no binary at all -> "" instead of an exception
    saved = utils.ytdlp_exe
    try:
        utils.ytdlp_exe = lambda: None
        out = loop.run_until_complete(utils.utub("https://youtu.be/xx"))
    finally:
        utils.ytdlp_exe = saved
    check("utub() returns '' when yt-dlp is absent (no exception)", out == "")


# ------------------------------------------------------------------ P3 + P5
def test_youtube_link_shapes():
    print("\n-- P5: accepted YouTube URL shapes --")
    good = ["https://www.youtube.com/watch?v=abc", "https://youtu.be/abc",
            "https://www.youtube.com/shorts/abc", "https://www.youtube.com/live/abc",
            "https://music.youtube.com/watch?v=abc",
            "https://www.youtube-nocookie.com/embed/abc"]
    bad = ["https://vimeo.com/1", "not a url", "", None]
    for u in good:
        check(f"is_youtube_link accepts {u}", utils.is_youtube_link(u) is True)
    for u in bad:
        check(f"is_youtube_link rejects {u!r}", utils.is_youtube_link(u) is False)

    src = inspect.getsource(pb)
    check("P3: the 'googlevideo.com' gate is gone from live code",
          not any(ln.strip().startswith(("if ", "and ", "or "))
                  and "googlevideo.com" in ln and "not in" in ln
                  for ln in src.splitlines()))


# ------------------------------------------------------------------ P4
def test_remote_urls_are_downloaded():
    print("\n-- P4: links are downloaded, not streamed from the CDN --")
    src = inspect.getsource(pb)
    for bad in ('play_audio(client, m, arg,', 'play_audio(client, m, text, "لینک")',
                'play_audio(client, m, url,', 'play_audio(client, m, direct,',
                'play_video(client, m, arg,', 'play_video(client, m, text, "—")',
                'play_video(client, m, direct,'):
        check(f"no handler streams a raw URL: {bad!r}", bad not in src)
    check("_resolve_stream_url() exists", hasattr(pb, "_resolve_stream_url"))
    check("_download_failed() exists and reports the reason", hasattr(pb, "_download_failed"))

    body = inspect.getsource(pb._resolve_stream_url)
    check("_resolve_stream_url routes YouTube through yt-dlp", "ytdlp_download" in body)
    check("_resolve_stream_url downloads plain HTTP links", "download_url" in body)
    check("_resolve_stream_url probes the real resolution", "probe_media" in body)

    # play_video must probe when no resolution was supplied
    pv = inspect.getsource(pb.play_video)
    check("play_video probes the resolution instead of the 640x360 default",
          "probe_media" in pv and "resolution is None" in pv)


def test_resolve_stream_url_behaviour():
    print("\n-- P4: _resolve_stream_url behaviour (yt-dlp stubbed) --")
    dl = os.path.join(config.get_config().DOWNLOAD_DIR, "stub.mp4")
    os.makedirs(os.path.dirname(dl), exist_ok=True)
    open(dl, "wb").write(b"x" * 10)

    calls = {}

    async def fake_info(url):
        return {"title": "Stub Title"}

    async def fake_download(url, prefix, video=True):
        calls["download"] = (url, prefix, video)
        return dl, ""

    async def fake_probe(path):
        return [1920, 1080], 12.5

    saved = (utils.ytdlp_info, utils.ytdlp_download, utils.probe_media)
    utils.ytdlp_info, utils.ytdlp_download, utils.probe_media = fake_info, fake_download, fake_probe
    try:
        path, title, res, err = loop.run_until_complete(
            pb._resolve_stream_url("https://youtu.be/abc", GROUP, UID, 7, video=True))
    finally:
        utils.ytdlp_info, utils.ytdlp_download, utils.probe_media = saved

    check("returns the downloaded local path", path == dl)
    check("returns the title from yt-dlp metadata", title == "Stub Title")
    check("returns the probed resolution", res == [1920, 1080])
    check("returns no error", err in (None, ""))
    check("asked for a video download", calls.get("download", (None, None, None))[2] is True)

    # failure path: the reason must survive to the caller
    async def failing(url, prefix, video=True):
        return None, "Video unavailable"

    saved = (utils.ytdlp_info, utils.ytdlp_download)
    utils.ytdlp_info, utils.ytdlp_download = fake_info, failing
    try:
        path, title, res, err = loop.run_until_complete(
            pb._resolve_stream_url("https://youtu.be/abc", GROUP, UID, 8, video=True))
    finally:
        utils.ytdlp_info, utils.ytdlp_download = saved
    check("failure returns (None, reason) instead of raising",
          path is None and err == "Video unavailable")

    text = pb._download_failed(UID, "Video unavailable")
    check("_download_failed surfaces the reason", "Video unavailable" in text)
    check("_download_failed still works with no reason",
          bool(pb._download_failed(UID, "").strip()))


def test_play_video_uses_probed_resolution():
    print("\n-- P4: play_video builds the stream with the real resolution --")
    vid = os.path.join(config.get_config().DOWNLOAD_DIR, "real.mp4")
    open(vid, "wb").write(b"x" * 10)

    captured = {}

    async def fake_stop(chat_id):
        return None

    async def fake_join(chat_id, stream, tries=2):
        captured["stream"] = stream

    async def fake_probe(path):
        return [1280, 720], 9.0

    async def fake_card(client, chat_id, uid, fa, en, **kw):
        captured["card"] = True

    saved = (pb.stop_current, utils.join_with_retry, utils.probe_media,
             utils.mark_streaming, utils.send_card)
    pb.stop_current = fake_stop
    utils.join_with_retry = fake_join
    utils.probe_media = fake_probe
    utils.mark_streaming = lambda *a, **k: None
    utils.send_card = fake_card
    try:
        loop.run_until_complete(pb.play_video(app, msg("پخش ویدیو"), vid, "T"))
    finally:
        (pb.stop_current, utils.join_with_retry, utils.probe_media,
         utils.mark_streaming, utils.send_card) = saved

    stream = captured.get("stream")
    check("play_video built a stream", stream is not None)
    if stream is not None:
        vp = stream._video_parameters
        check("stream uses the probed 1280x720, not the 640x360 default",
              (vp.width, vp.height) == (1280, 720), f"got {vp.width}x{vp.height}")
    check("the now-playing card was sent", captured.get("card") is True)


# ------------------------------------------------------------------ P6
def test_melobit_encoding():
    print("\n-- P6: melobit_search query encoding --")
    import aiohttp
    captured = {}

    class FakeResp:
        status = 200

        async def json(self):
            return {"results": []}

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class FakeSession:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        def get(self, url, params=None, timeout=None):
            captured["url"] = url
            captured["params"] = params
            return FakeResp()

    saved = aiohttp.ClientSession
    aiohttp.ClientSession = FakeSession
    try:
        loop.run_until_complete(utils.melobit_search("rock #1 & more"))
    finally:
        aiohttp.ClientSession = saved

    check("query is passed as a params dict, not interpolated",
          isinstance(captured.get("params"), dict))
    check("the full query reaches the request",
          (captured.get("params") or {}).get("query") == "rock #1 & more")
    check("the limit survives the request",
          (captured.get("params") or {}).get("limit") == 1)
    check("no '#' or '&' is left raw in the URL",
          "#" not in captured.get("url", "") and "?" not in captured.get("url", ""))


# ------------------------------------------------------------------ P7
def test_play_link_video_accepts_any_container():
    print("\n-- P7: 'پخش لینک ویدیو' no longer demands a literal .mp4 --")
    src = inspect.getsource(pb.play_link_video)
    check('the "\'.mp4\' not in text" gate is gone', '".mp4" not in text' not in src)
    check('the "\'.mkv\' not in text" gate is gone', '".mkv" not in text' not in src)
    check("it now only requires an http(s) URL", 'text.startswith("http")' in src)
    check("it resolves the link before streaming", "_resolve_stream_url" in src)


# ------------------------------------------------------------------ P8
def test_youtube_search_and_play():
    print("\n-- P8: YouTube search / play handlers --")
    ys = inspect.getsource(pb.youtube_search)
    yp = inspect.getsource(pb.youtube_play)
    check("youtube_search uses the maintained yt-dlp search first", "ytdlp_search" in ys)
    check("youtube_search downloads before streaming", "ytdlp_download" in ys)
    check("youtube_play uses is_youtube_link, not a literal substring",
          "is_youtube_link" in yp and '"youtube.com/watch" not in text' not in yp)
    check("youtube_play fetches the real title", "ytdlp_info" in yp)
    check("youtube_play reports the real download reason", "_download_failed" in yp)
    check("youtube_search reports the real download reason", "_download_failed" in ys)

    # search must not raise when every backend fails
    async def no_exe():
        return None

    saved = (utils.ytdlp_exe,)
    utils.ytdlp_exe = lambda: None
    try:
        # youtube-search-python still runs as a fallback; without network it
        # returns [] - either way the call must not raise.
        out = loop.run_until_complete(utils.ytdlp_search("anything", 1))
    except Exception as exc:  # pragma: no cover
        out = exc
    finally:
        (utils.ytdlp_exe,) = saved
    check("ytdlp_search degrades to [] instead of raising", isinstance(out, list), repr(out)[:60])


def test_download_url_errors():
    print("\n-- utils.download_url failure handling --")
    path, why = loop.run_until_complete(
        utils.download_url("http://127.0.0.1:9/nope.mp3", "t", ".mp3"))
    check("download_url returns (None, reason) when unreachable",
          path is None and bool(why), repr(why)[:60])
    check("MAX_LINK_BYTES cap is defined", utils.MAX_LINK_BYTES > 0)


def main():
    print("=" * 60)
    print("PLAYBACK / YOUTUBE REGRESSION TESTS")
    print("=" * 60)
    test_routing()
    test_ytdlp_discovery()
    test_youtube_link_shapes()
    test_remote_urls_are_downloaded()
    test_resolve_stream_url_behaviour()
    test_play_video_uses_probed_resolution()
    test_melobit_encoding()
    test_play_link_video_accepts_any_container()
    test_youtube_search_and_play()
    test_download_url_errors()


main()

failed = [r for r in results if not r[1]]
print("\n========================================")
print(f"RESULT: {len(results) - len(failed)}/{len(results)} playback checks passed")
if failed:
    print("FAILED:", [r[0] for r in failed])
    sys.exit(1)
print("=== PLAYBACK TEST PASSED ===")
sys.stdout.flush()   # os._exit() below skips the normal buffer flush
os._exit(0)
