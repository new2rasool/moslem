"""
MusicRasool - minimal conversation helper (replaces pyromod's `c.ask`).

Used by the admin panel to ask the owner/sudo for a value (user id,
group id, rate, broadcast text, ...). Each user can have one pending
question; the next private text message they send is delivered to the
registered handler.

IMPORTANT (Pyrogram dispatcher behaviour):
  the dispatcher runs only the FIRST matching handler of a group and
  then breaks. This handler is registered with a broad filter
  (`private & text`) so it matches EVERY private text message. When
  there is no pending question we MUST re-raise ContinuePropagation,
  otherwise every other private handler (e.g. the admin panel buttons)
  would be silently skipped - which is exactly why the developer panel
  buttons appeared to "do nothing".
"""
import time
import traceback

from pyrogram import ContinuePropagation, StopPropagation, filters
from pyrogram.types import Message

from clients import app

PENDING = {}  # uid -> {"handler": callable, "data": ..., "ts": float}

CANCEL_WORDS = {"/cancel", "/canncel", "لغو", "/skip"}

# A question that is never answered used to stay pending forever, so the
# user's NEXT private message - hours later - was silently consumed by the
# stale handler instead of reaching its real command.
TIMEOUT = 300  # seconds


def ask(uid, handler, data=None):
    PENDING[uid] = {"handler": handler, "data": data, "ts": time.time()}


def _expired(entry) -> bool:
    ts = entry.get("ts")
    return ts is not None and (time.time() - ts) > TIMEOUT


def cancel(uid):
    PENDING.pop(uid, None)


def is_pending(uid) -> bool:
    return uid in PENDING


@app.on_message(filters.private & filters.text, group=0)
async def _process_pending(client, m: Message):
    uid = m.from_user.id if m.from_user else m.chat.id
    entry = PENDING.get(uid)
    if entry is None or _expired(entry):
        # No pending conversation (or it timed out) - this message belongs to
        # other handlers (admin panel buttons, /login wizard, commands, ...).
        # Let them run.
        PENDING.pop(uid, None)
        raise ContinuePropagation
    cancel(uid)
    text = (m.text or "").strip()  # see utils.msg_text: captions have text=None
    if text in CANCEL_WORDS:
        await m.reply("• عملیات لغو شد !\n• Cancelled !")
        raise StopPropagation
    try:
        await entry["handler"](client, m, entry.get("data"))
    except Exception:
        traceback.print_exc()
    # consume the message - do not let other handlers react to it
    raise StopPropagation
