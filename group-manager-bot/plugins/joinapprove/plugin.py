"""پلاگین joinapprove — گیت ورودِ «تأیید توسط مدیر» (دکمه‌ای، بسیار دقیق).

جریان:
  ورود عضو → محدودسازی (restrict) + دکمه‌های «✅ تأیید» / «🚫 رد» برای مدیران.
  مدیر (ADMIN به بالا) تأیید کند → unrestrict + خوش‌آمد + ثبت join_approve.
  مدیر رد کند → kick + ثبت join_deny. تأیید/رد فقط توسط مدیران پذیرفته می‌شود.
  پایان مهلت (on_tick) → اخراج خودکار + ثبت auto:kick(joinapprove:timeout).

کاربرانی که در فهرست بن سراسری (gban) هستند اصلاً وارد صف نمی‌شوند.
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED

PLUGIN_VERSION = "1.0.0"

GBAN_KEY = "gban:list"
TTL_BUF_S = 5
# (chat,user) → {"deadline": …}
_pending: dict[tuple[int, int], dict] = {}


def _get(api, chat_id, key, default):
    group = api.groups.get(chat_id)
    return group.settings.get(key, default) if group else default


def _put(api, chat_id, key, value) -> None:
    from bot.repositories.base import Group

    group = api.groups.get(chat_id)
    if group is None:
        group = Group(chat_id=chat_id, settings={})
    group.settings[key] = value
    api.groups.upsert(group)


def register(api) -> None:
    async def on_join(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "ja_on", False):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return  # کارکنان نیازی به تأیید ندارند
        gbanned = dict(api.cache.get(GBAN_KEY) or {})
        if user_id in gbanned:
            return  # گارد بن سراسری بالاتر اولویت دارد؛ ورود را بن می‌کند
        timeout = int(_get(api, chat_id, "ja_timeout_s", 300))
        deadline = time.monotonic() + timeout
        _pending[(chat_id, user_id)] = {"deadline": deadline}
        ctx.act("restrict", user_id=user_id, reason="joinapprove:pending")
        buttons = [[
            {"text": "✅ تأیید ورود", "data": f"ja:a:{chat_id}:{user_id}"},
            {"text": "🚫 رد", "data": f"ja:r:{chat_id}:{user_id}"},
        ]]
        ctx.respond_buttons(
            api.tr(ctx.lang, "pending", user=user_id, secs=timeout), buttons)

    # ── پاسخ دکمهٔ مدیر ─────────────────────────────────────────────
    async def on_admin_button(ctx) -> None:
        parts = ctx.payload.split(":")
        if len(parts) < 3:
            return
        try:
            decision, chat_id, user_id = parts[0], int(parts[1]), int(parts[2])
        except ValueError:
            return
        # فقط مدیران می‌توانند تصمیم بگیرند
        if api.access.level(chat_id, ctx.user_id) < AccessLevel.ADMIN:
            ctx.respond(api.tr(ctx.lang, "staff_only"))
            return
        key = (chat_id, user_id)
        if key not in _pending:
            ctx.respond(api.tr(ctx.lang, "no_pending", user=user_id))
            return
        _pending.pop(key, None)
        if decision == "a":
            ctx.act("unrestrict", user_id=user_id, reason="joinapprove:approved")
            ctx.respond(api.tr(ctx.lang, "approved", user=user_id))
            await api.record_action(chat_id, "join_approve", user_id, ctx.user_id,
                                    reason="تأیید ورود توسط مدیر")
        elif decision == "r":
            ctx.act("kick", user_id=user_id, reason="joinapprove:denied")
            ctx.respond(api.tr(ctx.lang, "denied", user=user_id))
            await api.record_action(chat_id, "join_deny", user_id, ctx.user_id,
                                    reason="رد ورود توسط مدیر")

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_joinapprove(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "ja_on", False)
            t = _get(api, ctx.chat_id, "ja_timeout_s", 300)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, secs=t))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "ja_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "ja_on", False)
            _pending.clear()
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_joinapprove_time(ctx):
        try:
            t = int((ctx.args or "").strip())
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_time"))
            return
        if not 10 <= t <= 3600:
            ctx.respond(api.tr(ctx.lang, "usage_time"))
            return
        _put(api, ctx.chat_id, "ja_timeout_s", t)
        ctx.respond(api.tr(ctx.lang, "time_set", secs=t))

    api.register_event(EVENT_MEMBER_JOINED, on_join, priority=550)
    api.register_callback("ja:", on_admin_button)
    api.register_command("joinapprove", cmd_joinapprove, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("joinapprove",),
                         usage="joinapprove [on|off]")
    api.register_command("setapprovetime", cmd_joinapprove_time,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setapprovetime",),
                         usage="setapprovetime <10-3600>")


async def on_tick(api) -> None:
    """مهلت‌سنج — اخراج خودکار درخواست‌های بدون پاسخ (از میزبان)."""
    now = time.monotonic()
    expired = [k for k, st in _pending.items() if st["deadline"] <= now]
    for (chat_id, user_id) in expired:
        _pending.pop((chat_id, user_id), None)
        api.host.send_text(chat_id, api.tr("fa", "timeout", user=user_id))
        api.host.push_action(chat_id, {"type": "kick", "user_id": user_id,
                                       "reason": "joinapprove:timeout"})
        await api.record_action(chat_id, "auto:kick", user_id, 0,
                                reason="joinapprove:timeout")


def on_unload(api) -> None:
    _pending.clear()
