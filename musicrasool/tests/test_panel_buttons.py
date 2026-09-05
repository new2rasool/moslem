"""
Dispatcher-level test for the owner/sudo panel buttons.

IMPORTANT: in Pyrogram 2.x, handler registration happens via
`loop.create_task` inside the decorators. To register handlers, a
running event loop must exist BEFORE the modules are imported.
We therefore create + set the loop at the very top of this file and
run everything on that same loop (mirroring what `app.run()` does in
production).

The test then simulates the REAL dispatcher pipeline (group-by-group,
first matching handler per group, ContinuePropagation / StopPropagation
semantics) using REAL pyrogram.types.Message objects, and verifies that
EVERY button of the developer panel:

  1. reaches its handler (NOT swallowed by the broad
     `convo._process_pending` / `auth.login_flow` text handlers), and
  2. produces a visible reply (or registers a conversation prompt).

This is a regression test for the bug where the panel buttons "did
nothing" because `convo._process_pending` matched every private text
message first and the dispatcher broke out of the group.
"""
import asyncio
import inspect
import os
import sys
from types import SimpleNamespace

import pyrogram

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
os.chdir(PROJECT_ROOT)

with open(".env", "w", encoding="utf-8") as f:
    f.write("API_ID=1234567\nAPI_HASH=0123456789abcdef0123456789abcdef\n")
    f.write("BOT_TOKEN=123456:TESTTOKEN\nOWNER_ID=6173234874\nSUDO_ID=6173234874\n")
    f.write("DEFAULT_LANG=fa\nDOWNLOAD_DIR=downloads\n")

# ---- create + set the event loop BEFORE imports (handler registration) ----
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

import config  # noqa: E402
import database  # noqa: E402

config.load_config()
database.init_db()
for _t in ("charge", "charge2", "gp", "creators", "musicadmin", "videoadmins", "sudo", "alll", "ejbar", "banlist"):
    database.execute(f"DELETE FROM {_t}")

import convo  # noqa: E402
import handlers.private  # noqa: E402,F401
import handlers.auth  # noqa: E402,F401
import handlers.admin_panel  # noqa: E402,F401
import handlers.group_admin  # noqa: E402,F401
import handlers.playback  # noqa: E402,F401
import handlers.tv  # noqa: E402,F401
import handlers.misc  # noqa: E402,F401

from clients import app  # noqa: E402
from pyrogram import enums  # noqa: E402
from pyrogram.types import Chat, Message, User  # noqa: E402

OWNER = config.get_config().OWNER_ID

PRIVATE_CHAT = Chat(id=OWNER, type=enums.ChatType.PRIVATE, title="Private")
OWNER_USER = User(id=OWNER, first_name="Mersad", username="mersad", is_self=False)


def make_msg(text):
    msg = Message(id=1, chat=PRIVATE_CHAT, from_user=OWNER_USER, text=text)
    msg.replies = []

    async def fake_reply(t, **kw):
        msg.replies.append(t)
        return msg

    # instance attributes shadow the class methods (safe for tests)
    msg.reply = fake_reply
    msg.reply_text = fake_reply
    return msg


class FakeClient:
    def __init__(self):
        self.me = SimpleNamespace(username="test_bot")

    async def send_message(self, chat_id, text, **kw):
        return make_msg(text)

    async def get_chat(self, chat_id, *a, **k):
        return PRIVATE_CHAT

    async def get_chat_members(self, chat_id, filter=None):
        async def gen():
            return
            yield  # pragma: no cover

        return gen()

    async def get_chat_photos(self, user_id, limit=1):
        return []

    async def copy_message(self, chat_id, from_id, msg_id):
        return True


fake_client = FakeClient()

results = []


def check(name, cond):
    results.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), "-", name)


async def dispatch(client, msg):
    """Mirror the real Pyrogram handler_worker for this message."""
    ran = []
    for group in sorted(app.dispatcher.groups.keys()):
        for handler in app.dispatcher.groups[group]:
            try:
                if not await handler.check(client, msg):
                    continue
            except Exception:
                continue
            try:
                cb = handler.callback
                if inspect.iscoroutinefunction(cb):
                    await cb(client, msg)
                else:
                    await cb(client, msg)
            except pyrogram.ContinuePropagation:
                continue
            except pyrogram.StopPropagation:
                ran.append(handler.callback)
                break
            except Exception as exc:
                ran.append(("ERROR", handler, exc))
                break
            ran.append(handler.callback)
            break
    return ran


EXPECTED = {
    "📊 وضعیت": "vaziat",
    "📑 دریافت فاکتور": "invoice",
    "📆 میزان اعتبار": "credit_check",
    "تنظیم نرخ پایه": "rate_base",
    "تنظیم نرخ ویدیو": "rate_video_sudo",
    "تنظیم نرخ موزیک": "rate_music_sudo",
    "نرخ فروش موزیک": "rate_music_sale",
    "نرخ فروش ویدیو": "rate_video_sale",
    "📨 ارسال همگانی": "broadcast_users",
    "📨 ارسال همگانی گروه ها": "broadcast_groups",
    "▪️اجبار ورود فعال": "join_on",
    "▫️اجبار ورود غیرفعال": "join_off",
    "📋 لیست گروه های فعال موزیک": "list_music_active",
    "📁 لیست گروه های تمدید موزیک": "list_music_renew",
    "📋 لیست گروه های فعال ویدیو": "list_video_active",
    "📁 لیست گروه های تمدید ویدیو": "list_video_renew",
    "⚠️ لیست گروه های فاقد اعتبار": "list_no_credit",
    "❌ حذف سودو": "del_sudo_pv",
    "📌 تنظیم سودو": "add_sudo_pv",
    "❌ حذف ادمین": "del_admin_pv",
    "📌 تنظیم ادمین": "add_admin_pv",
    "👥 لیست سودو های ربات": "sudo_list",
    "🗑 حذف گروه ویدیو": "del_group_video",
    "🗑 حذف گروه موزیک": "del_group_music",
    "📬 ارسال به سودو": "send_to_sudo",
    "✏️ تنظیم استارت": "set_start",
    "📚 تنظیم درباره ما": "set_about",
    "📬 تنظیم پیامرسان": "set_payamresan",
    "📥 تنظیم پی وی": "set_pv",
    "📢 تنظیم کانال": "set_channel",
    "👥 تنظیم گروه": "set_group",
    "تنظیم محدودیت 🔏": "set_limit",
    "✏️ تنظیم استارت هلپر": "set_start_helper",
    "محدودیت نصب فعال ⚠️": "limit_on",
    "محدودیت نصب غیرفعال ♻️": "limit_off",
    "▪️ خروج خودکار فعال": "autoleft_on",
    "▫️ خروج خودکار غیرفعال": "autoleft_off",
}


async def main():
    # give the registration tasks (created by the decorators) time to run
    await asyncio.sleep(0.3)

    total_handlers = sum(len(v) for v in app.dispatcher.groups.values())
    if total_handlers == 0:
        print("FAIL - no handlers registered (event loop issue)")
        sys.exit(1)
    check("handlers registered", total_handlers > 0)

    failed_buttons = []
    for btn, expected in EXPECTED.items():
        convo.PENDING.clear()
        handlers.auth.LOGIN_STATE.clear()
        msg = make_msg(btn)
        ran = await dispatch(fake_client, msg)

        if not ran:
            failed_buttons.append((btn, "no handler ran"))
            continue

        first = ran[0]
        name = getattr(first, "__name__", str(first))
        mod = getattr(first, "__module__", "")

        if isinstance(first, tuple) and first[0] == "ERROR":
            failed_buttons.append((btn, f"handler error: {first[2]}"))
            continue

        if name != expected or mod != "handlers.admin_panel":
            failed_buttons.append((btn, f"wrong handler {mod}.{name} != {expected}"))
            continue

        if not msg.replies:
            failed_buttons.append((btn, "no reply produced"))
            continue

    for btn, err in failed_buttons:
        print(f"FAIL - button {btn!r}: {err}")
        check(f"panel button works: {btn}", False)
    for btn in EXPECTED:
        if not any(btn == b for b, _ in failed_buttons):
            check(f"panel button works: {btn}", True)

    # ----- convo still works (regression) -----
    convo.PENDING.clear()
    handlers.auth.LOGIN_STATE.clear()
    m_ask = make_msg("📌 تنظیم سودو")
    await dispatch(fake_client, m_ask)
    check("convo: button registers pending question", convo.is_pending(OWNER))

    convo.PENDING[OWNER] = {"handler": _fake_answer, "data": None}
    m_ans = make_msg("5555")
    ran = await dispatch(fake_client, m_ans)
    check("convo: answer consumed by convo handler",
          len(ran) == 1 and getattr(ran[0], "__name__", "") == "_process_pending")
    check("convo: answer processed", m_ans.replies != [])

    # ----- /start command still works -----
    convo.PENDING.clear()
    handlers.auth.LOGIN_STATE.clear()
    m_start = make_msg("/start")
    ran = await dispatch(fake_client, m_start)
    check("/start still works", ran and getattr(ran[0], "__name__", "") == "startt")

    failed = [r for r in results if not r[1]]
    print("\n========================================")
    print(f"RESULT: {len(results) - len(failed)}/{len(results)} checks passed")
    if failed:
        print("FAILED:", [r[0] for r in failed])
        sys.exit(1)
    print("=== PANEL BUTTONS TEST PASSED ===")


async def _fake_answer(client, m, data):
    await m.reply("answer processed OK")


if __name__ == "__main__":
    try:
        loop.run_until_complete(main())
    finally:
        try:
            loop.close()
        except Exception:
            pass
    os._exit(0 if all(r[1] for r in results) else 1)
