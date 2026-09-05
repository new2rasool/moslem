"""
MusicRasool - main entry point.

Starts the bot client, the helper userbot (if a session exists) and
PyTgCalls, launches the background tasks and blocks until stopped.
"""
import asyncio
import logging
import sys

from pyrogram import idle

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("pytgcalls").setLevel(logging.WARNING)

import config          # noqa: E402
import database        # noqa: E402

cfg = config.load_config()

# import handler & callback modules so decorators register
import handlers.private      # noqa: E402,F401
import handlers.auth         # noqa: E402,F401
import handlers.admin_panel  # noqa: E402,F401
import handlers.group_admin  # noqa: E402,F401
import handlers.playback     # noqa: E402,F401
import handlers.tv           # noqa: E402,F401
import handlers.misc         # noqa: E402,F401
import callbacks.router      # noqa: E402,F401
import callbacks.events      # noqa: E402,F401
import tasks                 # noqa: E402,F401

from clients import (  # noqa: E402
    app,
    call_py,
    ubot,
    helper_session_exists,
    helper_ready,
    set_helper_online,
)


async def entry():
    """Async entry (runs inside the client's event loop via app.run)."""
    return await main()


def run():
    """Sync entry - must use app.run() so the client's event loop (created
    at import time) is reused and module-level handler registration tasks
    are executed. asyncio.run() would create a NEW loop and handlers would
    never register."""
    from clients import app
    app.run(entry())


async def main():
    database.init_db()
    print("=" * 56)
    print("  MusicRasool is starting ...")
    print(f"  Owner: {cfg.OWNER_ID}   Sudo: {cfg.SUDO_ID}")
    print(f"  Helper session: {'FOUND' if helper_session_exists() else 'MISSING'}")
    print("=" * 56)

    # ------------------------------------------------------------------
    # 1. Start the BOT
    # ------------------------------------------------------------------
    await app.start()
    me = await app.get_me()
    print(f"  Bot online: @{me.username} (id {me.id})")

    # ------------------------------------------------------------------
    # 2. Start the HELPER userbot + PyTgCalls
    # ------------------------------------------------------------------
    helper_ok = False
    if helper_session_exists():
        try:
            await ubot.start()
            helper = await ubot.get_me()
            print(f"  Helper online: {helper.first_name} (id {helper.id})")
            try:
                await call_py.start()
                helper_ok = True
                print("  PyTgCalls started.")
            except Exception as exc:
                print(f"  [!] PyTgCalls failed to start: {exc}")
        except Exception as exc:
            print(f"  [!] Helper login failed (invalid session?): {exc}")
            print("      Delete sessions/helper.session and run /login again.")
    else:
        print("  [!] No helper session - streaming disabled until /login")

    # Publish the outcome so the play paths gate on the real state instead of
    # on the mere presence of sessions/helper.session (see clients.helper_ready).
    set_helper_online(helper_ok)
    if helper_session_exists() and not helper_ready():
        print("  [!] A helper session file exists but the helper is NOT online.")
        print("      Streaming, TV and voice-chat commands are disabled until this")
        print("      is fixed - delete sessions/helper.session and run /login again.")

    # ------------------------------------------------------------------
    # 3. Background tasks
    # ------------------------------------------------------------------
    bg = asyncio.create_task(tasks.run_all_tasks())

    # ------------------------------------------------------------------
    # 4. Block until stopped
    # ------------------------------------------------------------------
    await idle()

    # ------------------------------------------------------------------
    # 5. Cleanup
    # ------------------------------------------------------------------
    bg.cancel()
    try:
        await call_py.stop()
    except Exception:
        pass
    try:
        await ubot.stop()
    except Exception:
        pass
    await app.stop()
    print("  MusicRasool stopped. Goodbye!")
    return 0


if __name__ == "__main__":
    run()
