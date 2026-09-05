"""
Handler integration test: drives the bot's handlers and callbacks with
fake Message / CallbackQuery / Client objects and asserts the database
and PyTgCalls side-effects. No network required.
"""
import asyncio
import os
import sys
from types import SimpleNamespace

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import _bootstrap  # noqa: F401  (redirects .env/DB/downloads into a temp sandbox)

import config  # noqa: E402
import database  # noqa: E402

config.load_config()
database.init_db()
_bootstrap.make_helper_session()

import handlers.private  # noqa: E402,F401
import handlers.admin_panel  # noqa: E402,F401
import handlers.group_admin  # noqa: E402,F401
import handlers.playback  # noqa: E402,F401
import handlers.tv  # noqa: E402,F401
import handlers.misc  # noqa: E402,F401
import callbacks.router  # noqa: E402,F401
import callbacks.panel as panel_cb  # noqa: E402
import callbacks.player as player_cb  # noqa: E402
import callbacks.tv as tv_cb  # noqa: E402
import callbacks.help as help_cb  # noqa: E402

from clients import app, call_py, ubot  # noqa: E402
import utils  # noqa: E402

OWNER = config.get_config().OWNER_ID

# clean state so the test is idempotent
for _t in ("charge", "charge2", "gp", "creators", "musicadmin", "videoadmins", "sudo", "alll"):
    database.execute(f"DELETE FROM {_t}")


# ----------------------------------------------------------------------
# Fakes
# ----------------------------------------------------------------------
class FakeUser:
    def __init__(self, id, first_name="Test", username="test"):
        self.id = id
        self.first_name = first_name
        self.username = username

    def mention(self, name=None):
        return f"[{name or self.first_name}](tg://user?id={self.id})"


class FakeChat:
    def __init__(self, id, title="Test Group", username=""):
        self.id = id
        self.title = title
        self.username = username
        self.type = "supergroup"
        self.invite_link = "https://t.me/+abc"

    @property
    def is_group(self):
        return True


class FakeAudio:
    file_name = "song.mp3"
    title = "song"
    duration = 60
    file_id = "FAKEID"


class FakeReplyMsg:
    audio = FakeAudio()
    voice = None
    video = None
    id = 555
    from_user = FakeUser(111, "ReplyUser")
    chat = SimpleNamespace(id=-1001234567890)

    async def download(self, file_name=""):
        os.makedirs(os.path.dirname(file_name), exist_ok=True) if os.path.dirname(file_name) else None
        return file_name


class FakeMessage:
    def __init__(self, chat, user, text="", reply=None):
        self.chat = chat
        self.from_user = user
        self.text = text
        self.id = 123
        self.reply_to_message = reply
        self.matches = []
        self.sent = []
        self.audio = None
        self.voice = None
        self.video = None

    async def reply(self, text, **kw):
        self.sent.append(("reply", text, kw))
        return FakeMessage(self.chat, self.from_user, text)

    async def reply_text(self, text, **kw):
        return await self.reply(text, **kw)

    async def edit(self, text, **kw):
        self.sent.append(("edit", text, kw))
        return self

    def stop_propagation(self):
        raise Exception("__STOP_PROPAGATION__")


class FakeCallbackMessage:
    def __init__(self, chat):
        self.chat = chat
        self.id = 999
        self.deleted = False
        self.sent = []

    async def edit_message_text(self, text, **kw):
        self.sent.append(("edit", text, kw))

    async def delete(self, **kw):
        self.deleted = True

    async def reply(self, text, **kw):
        self.sent.append(("reply", text, kw))


class FakeCallback:
    def __init__(self, data, user, chat):
        self.data = data
        self.from_user = user
        self.message = FakeCallbackMessage(chat)
        self.answers = []

    async def answer(self, text, show_alert=False):
        self.answers.append((text, show_alert))

    async def edit_message_text(self, text, **kw):
        self.message.sent.append(("edit", text, kw))

    async def edit_message_reply_markup(self, markup):
        self.message.markup = markup


class FakeClient:
    def __init__(self):
        self.sent = []
        self.photos = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append(("msg", chat_id, text, kw))
        return FakeMessage(FakeChat(chat_id), FakeUser(OWNER), text)

    async def send_photo(self, chat_id, photo, caption="", **kw):
        self.sent.append(("photo", chat_id, caption, kw))
        return True

    async def send_video(self, chat_id, video, caption="", **kw):
        self.sent.append(("video", chat_id, caption, kw))
        return True

    async def get_chat(self, chat_id, *a, **k):
        return FakeChat(int(chat_id))

    async def get_me(self):
        return FakeUser(999, "Bot")

    def get_chat_members(self, chat_id, filter=None):
        from pyrogram import enums

        class Member:
            status = enums.ChatMemberStatus.OWNER
            user = FakeUser(111, "Owner")

        async def gen():
            yield Member()

        return gen()

    async def get_chat_photos(self, user_id, limit=1):
        return []

    async def download_media(self, msg, file_name=""):
        if file_name:
            os.makedirs(os.path.dirname(file_name) or ".", exist_ok=True)
            with open(file_name, "w") as f:
                f.write("x")
        return file_name

    async def export_chat_invite_link(self, chat_id):
        return "https://t.me/+xyz"

    async def promote_chat_member(self, **kw):
        return True

    async def set_administrator_title(self, *a, **k):
        return True

    async def leave_chat(self, chat_id):
        return True

    async def copy_message(self, chat_id, from_id, msg_id):
        return True

    async def get_chat_member(self, chat_id, user_id):
        raise Exception("not member")


class FakePyTg:
    def __init__(self):
        self.joined = []
        self.leaved = []
        self.calls = {}

    async def join_group_call(self, chat_id, stream, **kw):
        self.joined.append((chat_id, type(stream).__name__))

    async def leave_group_call(self, chat_id):
        self.leaved.append(chat_id)

    async def pause_stream(self, chat_id): pass

    async def resume_stream(self, chat_id): pass

    async def mute_stream(self, chat_id): pass

    async def unmute_stream(self, chat_id): pass

    async def change_volume_call(self, chat_id, v): self.calls[chat_id] = v


fake_client = FakeClient()
fake_pytg = FakePyTg()
call_py.join_group_call = fake_pytg.join_group_call
call_py.leave_group_call = fake_pytg.leave_group_call
call_py.pause_stream = fake_pytg.pause_stream
call_py.resume_stream = fake_pytg.resume_stream
call_py.mute_stream = fake_pytg.mute_stream
call_py.unmute_stream = fake_pytg.unmute_stream
call_py.change_volume_call = fake_pytg.change_volume_call

OWNER_USER = FakeUser(OWNER, "Mersad", "mersad")
SUDO_USER = FakeUser(6173234874, "Sudo", "sudo")
GROUP = FakeChat(-1001234567890, "Music Group")
GROUP2 = FakeChat(-1009999999999, "Video Group")

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


async def main():
    # ============ 1. /start ============
    from handlers.private import startt
    m = FakeMessage(FakeChat(OWNER, "PM"), OWNER_USER, "/start")
    await startt(fake_client, m)
    check("start sends welcome", any("START" in str(s) for s in m.sent))
    check("start shows owner panel", any("خوش آمدید" in s[2] for s in fake_client.sent))

    # ============ 2. install panel ============
    from handlers.group_admin import install_panel
    m2 = FakeMessage(GROUP, OWNER_USER, "نصب")
    await install_panel(fake_client, m2)
    check("install panel keyboard", len(m2.sent) > 0 and "نصب" in str(m2.sent[0]))

    # ============ 3. callback: install video ============
    cb = FakeCallback("installvideo", OWNER_USER, GROUP2)
    await panel_cb.handle_panel(fake_client, cb, "installvideo")
    check("install video inserts gp status=1", database.query("SELECT idgp FROM gp WHERE idgp=? AND status=1", (GROUP2.id,)) != [])

    # ============ 4. callback: charge music 1 month ============
    cb2 = FakeCallback("1mah2", OWNER_USER, GROUP)
    await panel_cb.handle_panel(fake_client, cb2, "1mah2")
    check("charge music inserts charge", database.query("SELECT idgp FROM charge WHERE idgp=?", (GROUP.id,)) != [])
    check("charge music inserts creator", database.query("SELECT creator FROM creators WHERE idgp=?", (GROUP.id,)) != [])
    check("charge music inserts gp status=0", database.query("SELECT idgp FROM gp WHERE idgp=? AND status=0", (GROUP.id,)) != [])
    check("charge music success text", any("شارژ شد" in str(s) for s in cb2.message.sent))

    # ============ 5. callback: charge video 2 months ============
    cb3 = FakeCallback("2mah1", OWNER_USER, GROUP2)
    await panel_cb.handle_panel(fake_client, cb3, "2mah1")
    check("charge video inserts charge2", database.query("SELECT idgp FROM charge2 WHERE idgp=?", (GROUP2.id,)) != [])

    # ============ 6. player: pausee / closee ============
    utils.PLAYING[GROUP.id] = "/tmp/fake.mp3"
    cb4 = FakeCallback("pausee", OWNER_USER, GROUP)
    await player_cb.handle_player(fake_client, cb4, "pausee")
    check("player pausee answers", cb4.answers != [])

    cb5 = FakeCallback("closee", OWNER_USER, GROUP)
    await player_cb.handle_player(fake_client, cb5, "closee")
    check("player closee leaves call", GROUP.id in fake_pytg.leaved)
    check("player closee removes playing", GROUP.id not in utils.PLAYING)

    # access control: normal user cannot control player
    normal = FakeUser(777, "Normal")
    utils.PLAYING[GROUP.id] = "/tmp/fake2.mp3"
    cb6 = FakeCallback("closee", normal, GROUP)
    handled = await player_cb.handle_player(fake_client, cb6, "closee")
    check("player blocks non-admin", handled is False and GROUP.id in utils.PLAYING)
    utils.PLAYING.pop(GROUP.id, None)

    # ============ 7. TV callback ============
    cb7 = FakeCallback("tv1", OWNER_USER, GROUP)
    await tv_cb.handle_tv(fake_client, cb7, "tv1")
    check("tv1 streams AudioVideoPiped", any(c == GROUP.id and t == "AudioVideoPiped" for c, t in fake_pytg.joined))
    check("tv1 sets playing", GROUP.id in utils.PLAYING)
    utils.PLAYING.pop(GROUP.id, None)

    # ============ 8. help callbacks ============
    cb8 = FakeCallback("helpvideo", OWNER_USER, GROUP)
    await help_cb.handle_help(fake_client, cb8, "helpvideo")
    check("helpvideo shows text", any("سرچ" in str(s) for s in cb8.message.sent))

    # ============ 9. credit checks in group ============
    m3 = FakeMessage(GROUP, OWNER_USER, "پخش")
    m3.reply_to_message = FakeReplyMsg()
    access_before = database.insmusic()
    await handlers_playback_play_reply(fake_client, m3)
    check("play reply streams AudioPiped", any(c == GROUP.id and t == "AudioPiped" for c, t in fake_pytg.joined))

    # ============ 10. volume ============
    m4 = FakeMessage(GROUP, OWNER_USER, "صدای موزیک 100")
    from handlers.playback import volume_music
    utils.PLAYING[GROUP.id] = "/tmp/x.mp3"
    await volume_music(fake_client, m4)
    check("volume sets 100", fake_pytg.calls.get(GROUP.id) == 100)
    utils.PLAYING.pop(GROUP.id, None)

    # ============ 11. stop commands ============
    m5 = FakeMessage(GROUP, OWNER_USER, "توقف پخش")
    from handlers.playback import stopmusic
    utils.PLAYING[GROUP.id] = "/tmp/y.mp3"
    await stopmusic(fake_client, m5)
    check("stopmusic leaves call", GROUP.id in fake_pytg.leaved)

    # ============ 12. access: uncharged group blocked ============
    from handlers.playback import play_reply
    poor_group = FakeChat(-1004444444444, "Poor Group")
    m6 = FakeMessage(poor_group, OWNER_USER, "پخش")
    m6.reply_to_message = FakeReplyMsg()
    before = len(fake_pytg.joined)
    await play_reply(fake_client, m6)
    check("uncharged group blocked from play", len(fake_pytg.joined) == before)

    # ============ 13. group charge text command ============
    from handlers.group_admin import charge_music_group
    m7 = FakeMessage(GROUP, OWNER_USER, "تنظیم شارژ 30")
    try:
        await charge_music_group(fake_client, m7)
    except Exception as e:
        if "STOP_PROPAGATION" not in str(e):
            raise
    row = database.query("SELECT day FROM charge WHERE idgp=?", (GROUP.id,))
    check("group charge command updates days", row and row[0][0] == 30)

    # ============ 14. sudo list ============
    database.execute("DELETE FROM sudo WHERE idsudo=?", (5555,))
    database.execute("INSERT INTO sudo(idsudo, namesudo) VALUES(?,?)", (5555, "Sudoman"))
    check("sudo list shows sudo", database.idsudos() == [5555])

    # ============ 15. /play slash command (reply) ============
    from handlers.playback import slash_play
    m15 = FakeMessage(GROUP, OWNER_USER, "/play")
    m15.reply_to_message = FakeReplyMsg()
    before15 = len(fake_pytg.joined)
    await slash_play(fake_client, m15)
    check("/play reply streams AudioPiped", any(c == GROUP.id and t == "AudioPiped" for c, t in fake_pytg.joined[before15:]))
    check("/play registers stream for reconnect", GROUP.id in utils.STREAMS and utils.STREAMS[GROUP.id]["kind"] == "audio")
    utils.clear_streaming(GROUP.id)
    fake_pytg.joined.clear()
    fake_pytg.leaved.clear()

    # ============ 16. /skip playlist advance ============
    from handlers.playback import slash_skip, SKIP_EVENT
    utils.PLAYLIS[GROUP.id] = "running"
    m16 = FakeMessage(GROUP, OWNER_USER, "/skip")
    await slash_skip(fake_client, m16)
    check("/skip sets skip event", SKIP_EVENT.get(GROUP.id) is not None and SKIP_EVENT[GROUP.id].is_set())
    check("/skip replies", m16.sent != [])
    utils.PLAYLIS.pop(GROUP.id, None)
    SKIP_EVENT.pop(GROUP.id, None)

    # ============ 17. /skip stops a single stream ============
    utils.PLAYING[GROUP.id] = "/tmp/skipme.mp3"
    utils.STREAMS[GROUP.id] = {"kind": "audio", "path": "/tmp/skipme.mp3", "resolution": None, "fails": 0}
    m17 = FakeMessage(GROUP, OWNER_USER, "/skip")
    await slash_skip(fake_client, m17)
    check("/skip stops single stream", GROUP.id not in utils.PLAYING and GROUP.id not in utils.STREAMS)

    # ============ 18. local file playback (PlayFile) ============
    from handlers.playback import play_file_cmd
    local_file = os.path.join(config.get_config().DOWNLOAD_DIR, "local_test.mp3")
    with open(local_file, "w") as f:
        f.write("fake")
    m18 = FakeMessage(GROUP, OWNER_USER, f"PlayFile {local_file}")
    before18 = len(fake_pytg.joined)
    await play_file_cmd(fake_client, m18)
    check("PlayFile streams local mp3", any(c == GROUP.id and t == "AudioPiped" for c, t in fake_pytg.joined[before18:]))
    utils.clear_streaming(GROUP.id)
    os.remove(local_file)

    # ============ 19. watch_streams reconnects dropped stream ============
    import tasks
    import time as _t

    async def _binding_false(chat_id):
        return False

    tasks._binding_active = _binding_false
    utils.STREAMS[GROUP.id] = {"kind": "audio", "path": "/tmp/watched.mp3", "resolution": None,
                               "fails": 0, "started_at": _t.time() - 60, "ignore_until": 0,
                               "duration": None, "retries": 0}
    before19 = len(fake_pytg.joined)
    await tasks._watch_once()
    check("watchdog reconnects dropped stream", any(c == GROUP.id and t == "AudioPiped" for c, t in fake_pytg.joined[before19:]))
    check("watchdog resets fail counter", utils.STREAMS[GROUP.id]["fails"] == 0)
    utils.clear_streaming(GROUP.id)
    fake_pytg.joined.clear()

    # ============ 20. watch_streams gives up after repeated failures ============
    async def _boom(chat_id, stream, **kw):
        raise RuntimeError("network down")

    real_join = call_py.join_group_call
    call_py.join_group_call = _boom
    utils.STREAMS[GROUP.id] = {"kind": "audio", "path": "/tmp/watched.mp3", "resolution": None,
                               "fails": 4, "started_at": _t.time() - 60, "ignore_until": 0,
                               "duration": None, "retries": 0}
    await tasks._watch_once()
    check("watchdog gives up after repeated failures", GROUP.id not in utils.STREAMS)
    call_py.join_group_call = real_join
    tasks._binding_active = tasks._binding_active  # restore (still the patched one is fine)

    # ============ summary ============
    failed = [r for r in results if not r[1]]
    print("\n========================================")
    print(f"RESULT: {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:", [r[0] for r in failed])
        sys.exit(1)
    print("=== HANDLER TEST PASSED ===")


async def handlers_playback_play_reply(client, m):
    from handlers.playback import play_reply
    # call directly but avoid require_helper (no helper session in test)
    await play_reply(client, m)


if __name__ == "__main__":
    asyncio.run(main())
    import os
try:
    os.remove(_bootstrap.HELPER_SESSION)
except FileNotFoundError:
    pass
os._exit(0 if all(r[1] for r in results) else 1)
