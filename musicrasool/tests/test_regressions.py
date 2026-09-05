"""
Regression tests for the defects listed in AUDIT.md.

Every check here corresponds to a bug that was found and fixed; the point of
this file is to make sure none of them can come back unnoticed.

Run directly:      python tests/test_regressions.py
Run with suite:    python tests/run_all.py
"""
import asyncio
import inspect
import os
import sys

import _bootstrap  # noqa: F401  (redirects .env/DB/downloads into a temp sandbox)
from _bootstrap import PROJECT_ROOT

# handler registration needs a running loop BEFORE the modules are imported
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import pyrogram  # noqa: E402
from pyrogram import enums  # noqa: E402
from pyrogram.types import Chat, Message, User  # noqa: E402

import config  # noqa: E402
import database  # noqa: E402

config.load_config()
database.init_db()

import clients  # noqa: E402
import i18n  # noqa: E402
import utils  # noqa: E402
import convo  # noqa: E402
import handlers.auth  # noqa: E402
import handlers.group_admin  # noqa: E402
import handlers.misc  # noqa: E402
import handlers.playback  # noqa: E402
import tasks  # noqa: E402
from callbacks import tv as tv_cb  # noqa: E402
from clients import app  # noqa: E402

UID = 6173234874
GROUP = -1001234567890
results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


# ----------------------------------------------------------------------
# fakes
# ----------------------------------------------------------------------
class FakeMessage:
    def __init__(self, chat_id=GROUP, text="x"):
        self.chat = type("C", (), {"id": chat_id, "title": "T"})()
        self.from_user = type("U", (), {"id": UID, "first_name": "O",
                                        "mention": staticmethod(lambda n: f"@{n}")})()
        self.id = 1
        self.text = text
        self.replies = []
        self.edits = []

    async def reply(self, text, **kw):
        self.replies.append(str(text))
        return FakeEditable()

    def continue_propagation(self):
        """Mirror pyrogram.types.Update.continue_propagation()."""
        raise pyrogram.ContinuePropagation()

    def stop_propagation(self):
        raise pyrogram.StopPropagation()


class FakeEditable:
    def __init__(self):
        self.edits = []

    async def edit(self, text, **kw):
        self.edits.append(str(text))

    async def edit_text(self, text, **kw):
        self.edits.append(str(text))


class FakeCallback:
    def __init__(self, data):
        self.data = data
        self.from_user = type("U", (), {"id": UID})()
        self.message = FakeMessage()
        self.answered = []
        self.edited = []
        self.deleted = 0

        outer = self

        class Msg:
            chat = outer.message.chat

            async def delete(self):
                outer.deleted += 1

        self.message.delete = Msg.delete
        self.message.chat = outer.message.chat

    async def answer(self, text=None, **kw):
        self.answered.append(text)

    async def edit_message_text(self, text, **kw):
        self.edited.append(str(text))


class KickedApp:
    """get_chat always fails - the bot was removed from the group."""

    def __init__(self):
        self.sent = []

    async def get_chat(self, cid):
        raise RuntimeError("bot was kicked from the chat")

    async def send_message(self, *a, **k):
        self.sent.append(a)
        return FakeEditable()

    async def send_photo(self, *a, **k):
        return FakeEditable()


# ----------------------------------------------------------------------
def _real_group_message(text):
    chat = Chat(id=GROUP, type=enums.ChatType.SUPERGROUP, title="T")
    user = User(id=UID, first_name="O", is_bot=False, is_verified=False,
                is_restricted=False, is_deleted=False, is_self=False)
    return Message(client=app, id=1, chat=chat, from_user=user, text=text)


def _handlers_for(func_name):
    out = []
    for group in app.dispatcher.groups.values():
        for h in group:
            cb = getattr(h, "callback", None)
            if cb is not None and getattr(cb, "__name__", "") == func_name:
                out.append(h)
    return out


async def main():
    # ==================================================================
    # H1 - force-join: `channel.status` must actually gate checkjoin
    # ==================================================================
    database.execute("DELETE FROM channel")
    database.execute("DELETE FROM ejbar")
    database.execute(
        "INSERT INTO channel(idchannel, namechannel, invite, status) VALUES(?,?,?,?)",
        (-100999, "Chan", "https://t.me/chan", 0),
    )

    class NotMember:
        async def get_chat_member(self, *a, **k):
            from pyrogram.errors import UserNotParticipant
            raise UserNotParticipant("x")

    m = FakeMessage()
    r = await utils.checkjoin(NotMember(), m, 4242)
    check("H1 force-join OFF (status=0) lets the user through", r is None)

    database.execute("UPDATE channel SET status=1 WHERE idchannel=?", (-100999,))
    m2 = FakeMessage()
    r2 = await utils.checkjoin(NotMember(), m2, 4242)
    check("H1 force-join ON (status=1) blocks a non-member", r2 is not None)
    check("H1 the user is told to join", any("کانال" in x for x in m2.replies))

    # exemptions still bypass it
    database.execute("INSERT INTO ejbar(idgp, idadmin) VALUES(?,?)", (GROUP, 4242))
    r3 = await utils.checkjoin(NotMember(), FakeMessage(), 4242)
    check("H1 exempt admins still bypass force-join", r3 is None)
    database.execute("DELETE FROM ejbar")
    database.execute("DELETE FROM channel")

    # ==================================================================
    # H3 - ping_cmd must let helper_ping run (ContinuePropagation)
    # ==================================================================
    hs = _handlers_for("ping_cmd")
    check("H3 ping_cmd is registered", len(hs) == 1)
    msg = _real_group_message("پینگ")
    matched = len(hs) == 1 and bool(await hs[0].filters(app, msg))
    check("H3 'پینگ' matches the ping filter", matched)

    real_sleep = asyncio.sleep

    async def fast_sleep(_d, *a, **k):
        return None

    asyncio.sleep = fast_sleep
    try:
        ping = handlers.misc.ping_cmd
        src = inspect.getsource(ping)
        propagated = False
        fm = FakeMessage(text="پینگ")
        fm.reply = _make_reply_returning(FakeEditable())
        try:
            await ping(None, fm)
        except pyrogram.ContinuePropagation:
            propagated = True
        check("H3 ping_cmd raises ContinuePropagation", propagated)
        check("H3 ping_cmd keeps the helper ping reachable",
              "continue_propagation" in src)
    finally:
        asyncio.sleep = real_sleep

    helper_hs = _handlers_for("helper_ping")
    check("H3 helper_ping is still registered", len(helper_hs) == 1)

    # the ping card must stay ONE message and report MEASURED numbers
    import datetime
    import re as _re2
    # check the AST, not the text - the explanatory comment in ping_cmd
    # mentions the old random.choice() on purpose
    import ast

    def _calls_random_choice(fn):
        tree = ast.parse(inspect.getsource(fn))
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "choice"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "random"):
                return True
        return False

    check("H3 ping no longer invents latency with random.choice",
          not _calls_random_choice(handlers.misc.ping_cmd)
          and not _calls_random_choice(handlers.misc.helper_ping))

    fm3 = FakeMessage(text="پینگ")
    fm3.date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=0.4)
    cards = []

    async def _reply_card(text, **kw):
        ed = FakeEditable()
        cards.append(ed)
        return ed

    fm3.reply = _reply_card
    asyncio.sleep = fast_sleep
    try:
        try:
            await handlers.misc.ping_cmd(None, fm3)
        except pyrogram.ContinuePropagation:
            pass
    finally:
        asyncio.sleep = real_sleep
    check("ping sends exactly one card (edited in place)", len(cards) == 1)
    final = cards[0].edits[-1] if cards and cards[0].edits else ""
    nums = _re2.findall(r"(\d+\.\d{3})", final)
    check("ping shows two measured latencies with 3 decimals", len(nums) == 2)
    check("ping 'receive' latency comes from the update timestamp",
          bool(nums) and 0.3 <= float(nums[0]) < 5.0)

    # ==================================================================
    # H5 - backtv must edit the panel, not delete-then-reply
    # ==================================================================
    cb = FakeCallback("backtv")
    handled = await tv_cb.handle_tv(None, cb, "backtv")
    check("H5 backtv handled", handled is True)
    check("H5 backtv edits the message in place", len(cb.edited) == 1)
    check("H5 backtv no longer deletes the message first", cb.deleted == 0)

    # the satellite "back" button must go back to the satellite list
    cb2 = FakeCallback("backma")
    await tv_cb.handle_tv(None, cb2, "backma")
    check("H5/backma satellite list is reachable", len(cb2.edited) == 1)
    check("H5 NATIONAL/satellite split is consistent",
          set(tv_cb.NATIONAL).issubset(set(tv_cb.CHANNELS)))

    # ==================================================================
    # H6 - helper_ready() must reflect the real start outcome
    # ==================================================================
    _bootstrap.make_helper_session()
    clients.set_helper_online(True)
    check("H6 helper_ready True when the helper started", clients.helper_ready() is True)
    clients.set_helper_online(False)
    check("H6 helper_ready False when the session file exists but start failed",
          clients.helper_ready() is False)
    check("H6 helper_session_exists still reports the file",
          clients.helper_session_exists() is True)
    clients.set_helper_online(True)
    _bootstrap.drop_helper_session()
    check("H6 helper_ready False with no session file", clients.helper_ready() is False)
    _bootstrap.make_helper_session()

    # ==================================================================
    # H7 - the expiry task must advance `status` even if get_chat fails
    # ==================================================================
    import time as _time
    database.execute("DELETE FROM charge")
    database.execute(
        "INSERT INTO charge(idgp, idadmin, day, start, end, status) VALUES(?,?,?,?,?,?)",
        # 1 hour left -> inside the 48h warning window but not yet expired,
        # so one pass can only move this row 0 -> 1
        (str(GROUP), UID, 30, 0, int(_time.time()) + 3600, 0),
    )
    real_app = tasks.app
    fake_app = KickedApp()
    tasks.app = fake_app

    class _StopTask(Exception):
        pass

    async def _sleep_except_long(d, *a, **k):
        if d >= 600:
            raise _StopTask()
        return None

    real_sleep2 = asyncio.sleep
    asyncio.sleep = _sleep_except_long
    try:
        await tasks.check_music_expiry()
    except _StopTask:
        pass
    except Exception as exc:
        print("   -> unexpected:", type(exc).__name__, exc)
    finally:
        asyncio.sleep = real_sleep2
        tasks.app = real_app

    tasks_sent = fake_app.sent
    rows = database.query("SELECT status FROM charge WHERE idgp=?", (str(GROUP),))
    check("H7 charge status advanced despite the failing get_chat",
          bool(rows) and int(rows[0][0]) == 1)
    check("H7 the owner was still notified with the raw ids",
          len(tasks_sent) > 0 and str(GROUP) in str(tasks_sent[0]))
    database.execute("DELETE FROM charge")

    # ==================================================================
    # H8 - پاکسازی must not delete files that are in a playlist
    # ==================================================================
    dl = config.get_config().DOWNLOAD_DIR
    folder = os.path.join(dl, str(GROUP))
    os.makedirs(folder, exist_ok=True)
    kept = os.path.join(folder, "keep_me.mp3")
    stray = os.path.join(dl, "stray.mp3")
    open(kept, "w").write("audio")
    open(stray, "w").write("temp")
    database.execute("DELETE FROM playlist")
    database.execute("INSERT INTO playlist(idgp, path, duration) VALUES(?,?,?)",
                     (GROUP, kept, 60))

    m = FakeMessage()
    await handlers.group_admin.clear_downloads(None, m)
    check("H8 playlist file survived پاکسازی", os.path.exists(kept))
    check("H8 unreferenced file was removed", not os.path.exists(stray))
    check("H8 the owner is told how many files were kept",
          any("نگه داشته شد" in r or "Kept" in r for r in m.replies))
    database.execute("DELETE FROM playlist")

    # ==================================================================
    # H11 - `PromoteMusic` must strip the command word
    # ==================================================================
    got = utils.clean_command("PromoteMusic @ali", "ترفیع موزیک", "PromoteMusic").lstrip("@")
    check("H11 PromoteMusic argument is stripped", got == "ali")
    import re as _re
    src = inspect.getsource(handlers.group_admin.promotemusic_arg)
    arg = _re.search(r'clean_command\([^,]+,\s*"[^"]*"\s*,\s*"([^"]+)"\)', src)
    check("H11 the handler strips 'PromoteMusic' (the name its filter accepts)",
          arg is not None and arg.group(1) == "PromoteMusic")

    # ==================================================================
    # H12 - mute / unmute text handlers must exist and match
    # ==================================================================
    for fname, words in (("mute_cmd", ["بیصدا", "silent"]),
                         ("unmute_cmd", ["باصدا", "unsilent"])):
        hs = _handlers_for(fname)
        check(f"H12 {fname} is registered", len(hs) == 1)
        if hs:
            ok = True
            for w in words:
                ok = ok and bool(await hs[0].filters(app, _real_group_message(w)))
            check(f"H12 {fname} matches {'/'.join(words)}", ok)

    # ==================================================================
    # S1 - PlayFile must stay inside DOWNLOAD_DIR
    # ==================================================================
    r = handlers.playback._resolve_local_media("/etc/passwd")
    check("S1 absolute path outside downloads is rejected", r is None)
    r = handlers.playback._resolve_local_media("../../../../etc/passwd")
    check("S1 ../ traversal is rejected", r is None)
    inside = os.path.join(dl, "ok.mp3")
    open(inside, "w").write("x")
    r = handlers.playback._resolve_local_media("ok.mp3")
    check("S1 a file inside downloads is accepted",
          r is not None and os.path.realpath(r) == os.path.realpath(inside))
    os.remove(inside)

    # ==================================================================
    # R - caption-only messages / None text
    # ==================================================================
    class CapOnly:
        text = None
        caption = "پخش something"

    check("R msg_text falls back to the caption",
          utils.msg_text(CapOnly()) == "پخش something")
    check("R msg_text never returns None", utils.msg_text(type("M", (), {})()) == "")
    check("R clean_command(None) does not become the string 'None'",
          utils.clean_command(None, "x", "y") == "")
    check("R brief_error hides the exception text",
          "Telegram says" not in utils.brief_error(pyrogram.errors.BadRequest("secret")))

    # ==================================================================
    # C2 / C3 / I2 - no shipped secrets, no placeholder .env, ffmpeg wiring
    # ==================================================================
    example = open(os.path.join(PROJECT_ROOT, ".env.example"), encoding="utf-8").read()
    # The literals below are the credentials that moslem.zip actually shipped.
    # They are repeated here on purpose: this test is the guard that proves
    # they can never be reintroduced. They must still be revoked via
    # @BotFather - removing them from a test does not un-leak them.
    leaked = ["8053868457", "9c9fe04dc2a85e9dd74208335c537f1a", "918990"]
    found = [s for s in leaked if s in example]
    check("C2 .env.example ships no real credentials", found == [])
    check("C2 .env.example uses placeholders", "PUT_YOUR_BOT_TOKEN_HERE" in example)
    # structural: no key may carry a real-looking value
    real_values = []
    for line in example.splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if value and "PUT_YOUR_" not in value and value not in ("fa", "en", "downloads"):
            real_values.append(key.strip())
    check("C2 no key in .env.example holds a real-looking value",
          real_values == [])

    for script in ("install.sh", "install.bat"):
        body = open(os.path.join(PROJECT_ROOT, script), encoding="utf-8").read()
        check(f"C3 {script} never copies .env.example over .env",
              "copy /y .env.example .env" not in body and "cp .env.example .env" not in body)
    sh = open(os.path.join(PROJECT_ROOT, "install.sh"), encoding="utf-8").read()
    check("I2 install.sh does not hard-code the imageio-ffmpeg file name",
          "ffmpeg-linux-x86_64-v7.0.2" not in sh and "get_ffmpeg_exe()" in sh)

    # an unedited .env.example must not crash Config() - it must look empty
    os.environ["API_ID"] = "PUT_YOUR_API_ID_HERE"
    os.environ["OWNER_ID"] = "PUT_YOUR_NUMERIC_USER_ID_HERE"
    try:
        c = config.Config()
        check("config: placeholder values are treated as unset (wizard runs)",
              c.API_ID == 0 and c.OWNER_ID == 0 and not c.is_complete())
    except Exception as exc:
        check("config: placeholder values are treated as unset (wizard runs)", False)
        print("   ->", type(exc).__name__, exc)
    finally:
        os.environ["API_ID"] = "1234567"
        os.environ["OWNER_ID"] = str(UID)

    # ==================================================================
    # misc: conversation questions expire
    # ==================================================================
    convo.ask(UID, lambda *a: None)
    entry = convo.PENDING[UID]
    entry["ts"] -= (convo.TIMEOUT + 1)
    check("convo: a stale question is detected as expired", convo._expired(entry))
    convo.ask(UID, lambda *a: None)
    check("convo: a fresh question is not expired",
          not convo._expired(convo.PENDING[UID]))
    convo.cancel(UID)

    # ==================================================================
    # misc: i18n language cache, Jalali date rendering
    # ==================================================================
    i18n._LANG_CACHE.clear()
    database.execute("DELETE FROM users")
    check("i18n: default language is Persian", i18n.lang_of(UID) == "fa")
    i18n.switch_lang(UID, "en")
    check("i18n: switch_lang updates the cache", i18n.lang_of(UID) == "en")
    check("i18n: t() follows the switch", i18n.t(UID, "fa-text", "en-text") == "en-text")
    i18n.switch_lang(UID, "fa")
    database.execute("DELETE FROM users")
    i18n.forget_lang(UID)

    # ==================================================================
    # docs vs reality: every command the help panels advertise must have a
    # handler. At audit time 4 of 79 (بیصدا/باصدا/silent/unsilent) had none.
    # ==================================================================
    import re as _re3
    help_src = open(os.path.join(PROJECT_ROOT, "callbacks", "help.py"),
                    encoding="utf-8").read()
    documented = set()
    for mm in _re3.finditer(r"✧\s*`([^`]+)`", help_src):
        tok = mm.group(1).strip()
        if tok.startswith("/"):
            tok = tok[1:]
        if tok and not tok.startswith("http"):
            documented.add(tok.lower())

    def _alternatives(pattern):
        out = []
        for part in _re3.split(r"\|", pattern):
            part = _re3.sub(r"\(\?<?[=!][^)]*\)", "", part)      # lookarounds first
            part = part.strip().strip("^$")
            part = _re3.sub(r"^\((.*)\)$", r"\1", part).strip("^$")
            part = _re3.sub(r"\[([A-Za-z])[A-Za-z]\]", r"\1", part)
            part = part.replace("(", "").replace(")", "").replace("^", "").replace("$", "")
            if part and _re3.fullmatch(r"[A-Za-z\u0600-\u06FF ]+", part):
                out.append(part.strip().lower())
        return out

    implemented = set()
    for _root, _dirs, _files in os.walk(PROJECT_ROOT):
        _dirs[:] = [d for d in _dirs if d not in
                    ("__pycache__", ".git", "venv", "downloads", "sessions", "tests")]
        for _fn in _files:
            if not _fn.endswith(".py"):
                continue
            _line_src = open(os.path.join(_root, _fn), encoding="utf-8").read()
            for _pat in _re3.findall(r'filters\.regex\(r"([^"]*)"', _line_src):
                implemented.update(_alternatives(_pat))
    missing = sorted(documented - implemented)
    check(f"docs: all {len(documented)} documented commands have a handler",
          missing == [])
    if missing:
        print("   -> missing:", missing)

    now_fa = utils.jalali_now()
    check("jalali_now renders a Persian weekday",
          any(d in now_fa for d in ("شنبه", "یک‌شنبه", "دوشنبه", "سه‌شنبه",
                                    "چهارشنبه", "پنج‌شنبه", "جمعه")))
    check("jalali_now(en) still returns the ASCII form",
          utils.jalali_now("en").isascii())


def _make_reply_returning(obj):
    async def _r(text, **kw):
        return obj
    return _r


loop.run_until_complete(main())

failed = [r for r in results if not r[1]]
print("\n========================================")
print(f"RESULT: {len(results) - len(failed)}/{len(results)} regression checks passed")
if failed:
    print("FAILED:", [r[0] for r in failed])
    sys.exit(1)
print("=== REGRESSION TEST PASSED ===")
sys.stdout.flush()   # os._exit() below skips the normal buffer flush
os._exit(0)
