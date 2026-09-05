"""
Stream-lifecycle tests (regression for "music stops after a few seconds
and the bot leaves the voice chat").

Root cause fixed:
  py-tgcalls' leave_group_call() -> binding.stop() makes ntgcalls fire
  the native stream-end callback, so a stale "stream ended" event from
  the PREVIOUS song can arrive right after the NEXT song started and
  make the bot leave the call.

Fixes verified here:
  1. stream-end events inside the ignore-window after a join are dropped
  2. early stream-ends (bad/partial file, network blip) are auto-retried
     (up to 2 times) instead of leaving the call
  3. after retries are exhausted the bot gives up and leaves cleanly
  4. during a playlist run the event handler never touches the call
  5. a stream that played long enough ends naturally -> clean leave
  6. ntgcalls 1.2.x status enum names are mapped (no KeyError)
"""
import asyncio
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

import _bootstrap  # noqa: F401  (redirects .env/DB/downloads into a temp sandbox)

import config  # noqa: E402
import database  # noqa: E402

config.load_config()
database.init_db()
for _t in ("charge", "charge2", "gp", "creators", "musicadmin", "videoadmins", "sudo", "alll", "ejbar", "banlist"):
    database.execute(f"DELETE FROM {_t}")

import utils  # noqa: E402
import callbacks.events as events  # noqa: E402,F401
import tasks  # noqa: E402
from clients import call_py  # noqa: E402


class FakePyTg:
    def __init__(self):
        self.joined = []
        self.leaved = []

    async def join_group_call(self, chat_id, stream, **kw):
        self.joined.append((chat_id, type(stream).__name__))

    async def leave_group_call(self, chat_id):
        self.leaved.append(chat_id)


fake_pytg = FakePyTg()
call_py.join_group_call = fake_pytg.join_group_call
call_py.leave_group_call = fake_pytg.leave_group_call

CHAT = -1001234567890
results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


class FakeUpdate:
    def __init__(self, chat_id):
        self.chat_id = chat_id


async def main():
    # ---------------------------------------------------------------
    # 1. stale event inside the ignore-window -> dropped
    # ---------------------------------------------------------------
    utils.clear_streaming(CHAT)
    entry = utils.mark_streaming(CHAT, "audio", "/tmp/song1.mp3", duration=240)
    # immediately fire an end event (ignore_until is now+6)
    await events.stream_end(fake_pytg, FakeUpdate(CHAT))
    check("stale end event inside ignore window is dropped",
          CHAT in utils.STREAMS and CHAT not in fake_pytg.leaved)

    # ---------------------------------------------------------------
    # 2. early end after the ignore window -> auto-retry (re-join)
    # ---------------------------------------------------------------
    utils.clear_streaming(CHAT)
    entry = utils.mark_streaming(CHAT, "audio", "/tmp/song2.mp3", duration=300)
    entry["started_at"] = time.time() - 5      # played only 5s of 300s
    entry["ignore_until"] = time.time() - 1    # window already over
    before = len(fake_pytg.joined)
    await events.stream_end(fake_pytg, FakeUpdate(CHAT))
    check("early end triggers a re-join",
          len(fake_pytg.joined) == before + 1
          and any(c == CHAT and t == "AudioPiped" for c, t in fake_pytg.joined[before:]))
    check("early end keeps the stream registered", CHAT in utils.STREAMS)
    check("early end increments retries", utils.STREAMS[CHAT]["retries"] == 1)

    # ---------------------------------------------------------------
    # 3. retries exhausted -> clean up + leave
    # ---------------------------------------------------------------
    utils.clear_streaming(CHAT)
    entry = utils.mark_streaming(CHAT, "audio", "/tmp/song3.mp3", duration=300, retries=2)
    entry["started_at"] = time.time() - 5
    entry["ignore_until"] = time.time() - 1
    fake_pytg.leaved.clear()
    await events.stream_end(fake_pytg, FakeUpdate(CHAT))
    check("retries exhausted -> clear + leave",
          CHAT not in utils.STREAMS and CHAT in fake_pytg.leaved)

    # ---------------------------------------------------------------
    # 4. playlist running -> handler never touches the call
    # ---------------------------------------------------------------
    utils.clear_streaming(CHAT)
    entry = utils.mark_streaming(CHAT, "audio", "/tmp/song4.mp3", duration=240)
    entry["ignore_until"] = time.time() - 1
    entry["started_at"] = time.time() - 5
    utils.PLAYLIS[CHAT] = "running"
    fake_pytg.leaved.clear()
    await events.stream_end(fake_pytg, FakeUpdate(CHAT))
    check("playlist: event handler does nothing",
          CHAT in utils.STREAMS and CHAT not in fake_pytg.leaved)
    utils.PLAYLIS.pop(CHAT, None)
    utils.clear_streaming(CHAT)

    # ---------------------------------------------------------------
    # 5. natural end after long enough -> clean leave
    # ---------------------------------------------------------------
    utils.clear_streaming(CHAT)
    entry = utils.mark_streaming(CHAT, "audio", "/tmp/song5.mp3", duration=60)
    entry["started_at"] = time.time() - 120   # played well past duration
    entry["ignore_until"] = time.time() - 1
    fake_pytg.leaved.clear()
    await events.stream_end(fake_pytg, FakeUpdate(CHAT))
    check("natural end -> clear + leave",
          CHAT not in utils.STREAMS and CHAT in fake_pytg.leaved)

    # ---------------------------------------------------------------
    # 6. watchdog is non-destructive when it cannot probe the call
    # ---------------------------------------------------------------
    async def _binding_none(chat_id):
        return None

    tasks._binding_active = _binding_none
    utils.clear_streaming(CHAT)
    entry = utils.mark_streaming(CHAT, "audio", "/tmp/song6.mp3", duration=240)
    entry["started_at"] = time.time() - 60
    before6 = len(fake_pytg.joined)
    await tasks._watch_once()
    check("watchdog does nothing when probe fails",
          CHAT in utils.STREAMS and len(fake_pytg.joined) == before6)
    utils.clear_streaming(CHAT)

    # ---------------------------------------------------------------
    # 7. the ntgcalls status enum used by this install is mapped in
    #    `call_py._conversions` (no KeyError in calls()/active_calls).
    #
    #    ntgcalls 1.1.x (the version pinned in requirements.txt) exposes
    #    TITLE-case members (Playing/Idling); ntgcalls 1.2.x renamed them
    #    to UPPERCASE (PLAYING/IDLING) and clients.py adds aliases for
    #    that case. Both are valid - assert whichever one is installed.
    # ---------------------------------------------------------------
    try:
        from ntgcalls import StreamStatus

        conv = call_py._conversions
        if hasattr(StreamStatus, "PLAYING"):
            # ntgcalls 1.2.x: the uppercase aliases must be present
            ok = StreamStatus.PLAYING in conv and StreamStatus.IDLING in conv
            label = "conversions map UPPERCASE 1.2.x members"
        else:
            # ntgcalls 1.1.x (pinned): the title-case members must be present
            ok = StreamStatus.Playing in conv and StreamStatus.Idling in conv
            label = "conversions map title-case 1.1.x members"
        check(label, ok)
    except Exception as exc:  # noqa: BLE001
        check("conversions map the installed ntgcalls status enum", False)
        print("   ->", type(exc).__name__, exc)

    # ---------------------------------------------------------------
    # summary
    # ---------------------------------------------------------------
    failed = [r for r in results if not r[1]]
    print("\n========================================")
    print(f"RESULT: {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:", [r[0] for r in failed])
        sys.exit(1)
    print("=== STREAM LIFECYCLE TEST PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())
    os._exit(0 if all(r[1] for r in results) else 1)
