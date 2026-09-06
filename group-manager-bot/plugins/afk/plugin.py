"""پلاگین afk — وضعیت «دور از دسترس» برای اعضا.

کاربر /afk [دلیل] می‌گذارد؛ اگر کسی او را «منشن» کند (با @username یا نام کامل
در متن)، ربات یک‌بار (هر ۵ دقیقه برای هر منشن‌کننده) اطلاع می‌دهد. با اولین
پیامِ خودِ کاربر، وضعیت AFK برداشته و خوش‌آمد گفته می‌شود. ورودی‌های کهنه
(بیش از ۲۴ ساعت) خودکار حذف می‌شوند.
"""

from __future__ import annotations

import time

from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

MAX_REASON = 120
AFK_TTL_S = 24 * 3600
NOTIFY_COOLDOWN_S = 300.0

# chat_id → user_id → {"name","username","reason","at","since"}
_afk: dict[int, dict[int, dict]] = {}
_notified: dict[tuple[int, int], float] = {}


def register(api) -> None:
    def _prune(chat_id: int) -> None:
        now = time.monotonic()
        store = _afk.get(chat_id)
        if not store:
            return
        for uid in [u for u, r in store.items() if now - r["at"] > AFK_TTL_S]:
            store.pop(uid, None)

    async def on_message(ctx) -> None:
        chat_id = ctx.chat_id
        user_id = ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        _prune(chat_id)
        store = _afk.get(chat_id)
        if not store:
            return

        # ۱) اگر خودِ گوینده AFK است و پیامِ عادی (نه فرمان) فرستاده → برداشتن
        if user_id in store and not raw.startswith("/"):
            me = store.pop(user_id)
            ctx.respond(api.tr(ctx.lang, "welcome_back", name=me["name"]))
            return

        # ۲) تشخیص منشن سایر اعضای AFK
        if not raw:
            return
        lowered = raw.lower()
        for uid, rec in list(store.items()):
            hit = False
            if rec.get("username"):
                hit = "@" + str(rec["username"]).lower() in lowered
            if not hit and rec.get("name") and len(rec["name"]) >= 5:
                hit = rec["name"].lower() in lowered
            if not hit:
                continue
            now = time.monotonic()
            nkey = (user_id, uid)
            if now - _notified.get(nkey, 0.0) < NOTIFY_COOLDOWN_S:
                break
            _notified[nkey] = now
            ctx.respond(api.tr(ctx.lang, "away", name=rec["name"],
                               reason=rec["reason"] or api.tr(ctx.lang, "no_reason"),
                               since=rec["since"]))
            break  # فقط یک اعلان در هر پیام

    async def cmd_afk(ctx):
        chat_id = ctx.chat_id
        reason = (ctx.args or "").strip()[:MAX_REASON]
        if reason.lower() in ("off", "برگشتم", "خاموش"):
            removed = _afk.get(chat_id, {}).pop(ctx.user_id, None)
            if removed:
                ctx.respond(api.tr(ctx.lang, "removed_manual"))
            else:
                ctx.respond(api.tr(ctx.lang, "not_afk"))
            return
        _afk.setdefault(chat_id, {})[ctx.user_id] = {
            "name": ctx.sender_name or str(ctx.user_id),
            "username": ctx.sender_username,
            "reason": reason,
            "at": time.monotonic(),
            "since": time.strftime("%H:%M"),
        }
        ctx.respond(api.tr(ctx.lang, "set", reason=reason or api.tr(ctx.lang, "no_reason")))

    api.register_event(EVENT_MESSAGE, on_message, priority=9)
    api.register_command("afk", cmd_afk, group_only=True, aliases=("afk",),
                         usage="afk [دلیل | off]")


def on_unload(api) -> None:
    _afk.clear()
    _notified.clear()
