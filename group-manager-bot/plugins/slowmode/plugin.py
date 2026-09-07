"""پلاگین slowmode — حالت آرام (فاصلهٔ اجباری بین پیام‌ها).

اعضای عادی فقط هر N ثانیه یک پیام می‌توانند بفرستند؛ پیام زودتر از موعد حذف و
هشدار داده می‌شود (کارکنان معاف). ساعت «اکنون» تزریق‌پذیر است تا تست قطعی باشد.
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

DEFAULT_SECONDS = 20
_last: dict[tuple[int, int], float] = {}


def _now() -> float:
    return time.monotonic()


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
    async def on_message(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "slowmode_on", False):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        if not raw:
            return  # فقط پیام‌های متنی مشمول فاصله‌گذاری می‌شوند
        seconds = int(_get(api, chat_id, "slowmode_seconds", DEFAULT_SECONDS))
        now = _now()
        key = (chat_id, user_id)
        last = _last.get(key)
        _last[key] = now
        if last is None or now - last >= seconds:
            return
        # خیلی زود → حذف + هشدار
        ctx.act("delete_message", user_id=user_id, reason="slowmode")
        ctx.respond(api.tr(ctx.lang, "too_fast", user=user_id, secs=seconds))

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_slowmode(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "slowmode_on", False)
            s = _get(api, ctx.chat_id, "slowmode_seconds", DEFAULT_SECONDS)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, secs=s))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "slowmode_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "slowmode_on", False)
            _last.clear()
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_setslowmode(ctx):
        try:
            seconds = int((ctx.args or "").strip())
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        if not 1 <= seconds <= 3600:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        _put(api, ctx.chat_id, "slowmode_seconds", seconds)
        ctx.respond(api.tr(ctx.lang, "set_ok", secs=seconds))

    api.register_event(EVENT_MESSAGE, on_message, priority=140)
    api.register_command("slowmode", cmd_slowmode, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("slowmode",),
                         usage="slowmode [on|off]")
    api.register_command("setslowmode", cmd_setslowmode, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("setslowmode",),
                         usage="setslowmode <1-3600 ثانیه>")


def on_unload(api) -> None:
    _last.clear()
