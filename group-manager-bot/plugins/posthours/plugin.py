"""پلاگین posthours — محدودیت ساعات ارسال پیام در گروه.

ادمین بازهٔ مجاز (مثل 08:00-22:00) را تعیین می‌کند؛ پیام‌های اعضای عادی خارج
از بازه حذف و هشدار داده می‌شوند (کارکنان معاف‌اند). بازهٔ گذرنده از نیمه‌شب
(مثل 22:00-08:00 = حالت شبانه) پشتیبانی می‌شود. منطق بازه در
domain/schedule.py خالص و «اکنون» برای تست تزریق‌پذیر است.
"""

from __future__ import annotations

from datetime import datetime, time as dtime

from bot.domain.roles import AccessLevel
from bot.domain.schedule import in_window, parse_range
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"


def _now() -> dtime:
    return datetime.now().time()


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


def _fmt(t: dtime) -> str:
    return t.strftime("%H:%M")


def register(api) -> None:
    async def on_message(ctx) -> None:
        chat_id = ctx.chat_id
        user_id = ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "posthours_on", False):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return  # کارکنان معاف‌اند
        raw_range = _get(api, chat_id, "post_hours", "")
        window = parse_range(raw_range)
        if window is None:
            return
        start, end = window
        if in_window(_now(), start, end):
            return
        # پیام خارج از ساعات مجاز → حذف + هشدار
        ctx.act("delete_message", user_id=user_id, reason="posthours")
        ctx.respond(api.tr(ctx.lang, "blocked", start=_fmt(start), end=_fmt(end)))

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_posthours(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "posthours_on", False)
            rng = _get(api, ctx.chat_id, "post_hours", "")
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, rng=rng or "—"))
            return
        arg = parts[0].lower()
        if arg in ("off", "خاموش"):
            _put(api, ctx.chat_id, "posthours_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
            return
        window = parse_range(arg)
        if window is None:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        _put(api, ctx.chat_id, "post_hours", arg)
        _put(api, ctx.chat_id, "posthours_on", True)
        ctx.respond(api.tr(ctx.lang, "enabled", start=_fmt(window[0]),
                           end=_fmt(window[1])))

    api.register_event(EVENT_MESSAGE, on_message, priority=160)
    api.register_command("posthours", cmd_posthours, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("posthours", "ساعات"),
                         usage="posthours <HH:MM-HH:MM|off>")


def on_unload(api) -> None:
    pass
