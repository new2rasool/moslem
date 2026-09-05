"""
Smoke test: imports every module (registering all handlers), initializes
the database, then runs the real startup path (app.run) with network
calls mocked. idles for a few seconds then verifies handler registration
and clean shutdown. ZERO errors expected.
"""
import asyncio
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ---- fake .env -----------------------------------------------------
import _bootstrap  # noqa: F401  (redirects .env/DB/downloads into a temp sandbox)

import pyrogram  # noqa: E402

# Patch pyrogram.idle BEFORE main is imported (main does `from pyrogram import idle`)
real_idle = pyrogram.idle


async def fake_idle(*a, **k):
    await asyncio.sleep(6)


pyrogram.idle = fake_idle

import config  # noqa: E402
import database  # noqa: E402

cfg = config.load_config()
database.init_db()

# clean state so the test is idempotent
for _t in ("charge", "charge2", "gp", "creators", "musicadmin", "videoadmins", "sudo", "alll", "ejbar", "banlist"):
    database.execute(f"DELETE FROM {_t}")

# ---- import everything (registers handlers) ------------------------
import handlers.private        # noqa
import handlers.auth           # noqa
import handlers.admin_panel    # noqa
import handlers.group_admin    # noqa
import handlers.playback       # noqa
import handlers.tv             # noqa
import handlers.misc           # noqa
import callbacks.router        # noqa
import callbacks.events      # noqa
import tasks                   # noqa
print("[OK] all modules imported, handlers registered")

from clients import app, call_py, ubot, helper_session_exists  # noqa

# ---- mock network layer ---------------------------------------------
async def fake_start(*a, **k):
    return None


async def fake_stop(*a, **k):
    return None


async def fake_get_me(*a, **k):
    class Me:
        id = 999
        username = "test_bot"
        first_name = "Test"

    return Me()


async def fake_pytg_start(*a, **k):
    print("[mock] PyTgCalls started")
    return None


async def fake_pytg_stop(*a, **k):
    print("[mock] PyTgCalls stopped")
    return None


app.start = fake_start
app.stop = fake_stop
app.get_me = fake_get_me
ubot.start = fake_start
ubot.stop = fake_stop
ubot.get_me = fake_get_me
call_py.start = fake_pytg_start
call_py.stop = fake_pytg_stop

# ---- database sanity ------------------------------------------------
assert database.query("SELECT * FROM information WHERE id=1") != []
assert database.query("SELECT * FROM money1") != []
assert database.query("SELECT * FROM paye") != []
assert database.query("SELECT * FROM startcli") != []
assert database.idsudos() == []
assert database.moz(0) == []
assert database.kir(0) == []
database.add_user(6173234874)
assert database.get_lang(6173234874) == "fa"
database.set_lang(6173234874, "en")
assert database.get_lang(6173234874) == "en"
database.set_lang(6173234874, "fa")
print("[OK] database helpers OK")

# ---- run the real startup path --------------------------------------
import main  # noqa: E402

main.run()
print("[OK] full startup + idle + shutdown completed without errors")

# ---- verify handlers are actually registered ------------------------
total = sum(len(v) for v in app.dispatcher.groups.values())
print(f"[OK] dispatcher registered handler-groups: {len(app.dispatcher.groups)}, total handlers: {total}")
if total == 0:
    print("[FAIL] no handlers registered!")
    sys.exit(1)

# ---- verify keyboards/helpers build ---------------------------------
import utils  # noqa: E402
import i18n  # noqa: E402

for kind in ("music", "video", "playlist"):
    utils.player_keyboard(6173234874, kind)
utils.tv_menu_keyboard(6173234874)
utils.tv_ir_keyboard(6173234874)
utils.tv_sat_keyboard(6173234874)
utils.help_keyboard(6173234874)
utils.install_keyboard(6173234874)
utils.delete_keyboard(6173234874)
utils.charge_menu_keyboard(6173234874)
utils.months_keyboard(6173234874, "1")
utils.months_keyboard(6173234874, "2")
utils.start_keyboard(6173234874, {"groupp": "g", "adminpv": "a", "payamresan": "p"}, "https://t.me/x")
i18n.language_keyboard(6173234874)
print("[OK] all keyboards built")

import os as _os
try:
    _os.remove(_bootstrap.HELPER_SESSION)
except FileNotFoundError:
    pass

print("\n=== SMOKE TEST PASSED ===")
import os
_bootstrap.finish(0)
