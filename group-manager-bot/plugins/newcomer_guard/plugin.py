"""پلاگین newcomer_guard — گارد تازه‌واردان (سکوت موقت پس از ورود).

تازه‌واردها تا N دقیقه پس از پیوستن (پیش‌فرض ۱۰) اجازهٔ پیام ندارند؛ پیامشان
حذف و راهنمایی می‌شوند. کارکنان معاف‌اند. مکملِ کپچا/تأیید-مدیر است، نه جایگزین
آن‌ها. ساعت «اکنون» تزریق‌پذیر است تا تست قطعی باشد.
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED, EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

DEFAULT_MINUTES = 10
# chat_id → {user_id: زمان ورود (monotonic)}
_joined: dict[int, dict[int, float]] = {}


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
    async def on_join(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "ng_on", False):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        _joined.setdefault(chat_id, {})[user_id] = _now()

    async def on_message(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "ng_on", False):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        if raw.startswith("/"):
            return  # فرمان‌ها را نبند (دسترسی/help باید ممکن باشد)
        store = _joined.get(chat_id)
        if store is None or user_id not in store:
            return
        joined_at = store[user_id]
        minutes = int(_get(api, chat_id, "ng_minutes", DEFAULT_MINUTES))
        limit_s = minutes * 60
        if _now() - joined_at < limit_s:
            ctx.act("delete_message", user_id=user_id, reason="newcomer_guard")
            ctx.respond(api.tr(ctx.lang, "wait", user=user_id, minutes=minutes))
        else:
            store.pop(user_id, None)  # دوره تمام شد؛ دیگر پیگیری نکن

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_newcomer(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "ng_on", False)
            m = _get(api, ctx.chat_id, "ng_minutes", DEFAULT_MINUTES)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, minutes=m))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "ng_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "ng_on", False)
            _joined.pop(ctx.chat_id, None)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_newcomer_minutes(ctx):
        try:
            minutes = int((ctx.args or "").strip())
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_minutes"))
            return
        if not 1 <= minutes <= 1440:
            ctx.respond(api.tr(ctx.lang, "usage_minutes"))
            return
        _put(api, ctx.chat_id, "ng_minutes", minutes)
        ctx.respond(api.tr(ctx.lang, "minutes_set", minutes=minutes))

    api.register_event(EVENT_MEMBER_JOINED, on_join, priority=300)
    api.register_event(EVENT_MESSAGE, on_message, priority=130)
    api.register_command("newcomer", cmd_newcomer, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("newcomer",),
                         usage="newcomer [on|off]")
    api.register_command("newcomermin", cmd_newcomer_minutes,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("newcomermin",),
                         usage="newcomermin <1-1440 دقیقه>")


def on_unload(api) -> None:
    _joined.clear()
