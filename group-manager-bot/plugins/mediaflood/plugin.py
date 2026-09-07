"""پلاگین mediaflood — مهار سیلِ پیام‌های رسانه‌ای (عکس/ویدیو/گیف/استیکر/…).

رسانه‌های پشت‌سرهمِ یک عضو را در پنجرهٔ لغزان می‌شمارد (متن‌ها جدا حساب
می‌شوند)؛ عبور از آستانه → حذفِ رسانهٔ جدید + هشدارِ محدود. کارکنان معاف.
"""

from __future__ import annotations

import time
from collections import deque

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

MEDIA_TYPES = {"photo", "video", "animation", "document", "voice",
               "video_note", "sticker"}
DEFAULT_LIMIT = 5
DEFAULT_WINDOW = 60.0
WARN_COOLDOWN_S = 30.0

_buckets: dict[tuple[int, int], deque] = {}
_last_warn: dict[tuple[int, int], float] = {}


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
        if not _get(api, chat_id, "mf_on", False):
            return
        ctype = str(ctx.data.get("content_type") or "")
        if ctype not in MEDIA_TYPES:
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        limit = int(_get(api, chat_id, "mf_limit", DEFAULT_LIMIT))
        window = float(_get(api, chat_id, "mf_window_s", DEFAULT_WINDOW))
        now = time.monotonic()
        key = (chat_id, user_id)
        bucket = _buckets.setdefault(key, deque())
        while bucket and now - bucket[0] > window:
            bucket.popleft()
        bucket.append(now)
        if len(bucket) <= limit:
            return
        # حذف رسانهٔ جدید + هشدار (محدود)
        ctx.act("delete_message", user_id=user_id, reason="mediaflood")
        last = _last_warn.get(key)
        if last is None or now - last >= WARN_COOLDOWN_S:
            _last_warn[key] = now
            ctx.respond(api.tr(ctx.lang, "warn", user=user_id, limit=limit))

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_mediaflood(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "mf_on", False)
            l = _get(api, ctx.chat_id, "mf_limit", DEFAULT_LIMIT)
            w = _get(api, ctx.chat_id, "mf_window_s", DEFAULT_WINDOW)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, limit=l, window=int(w)))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "mf_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "mf_on", False)
            _buckets.clear()
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_setmediaflood(ctx):
        parts = (ctx.args or "").split()
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        try:
            limit = int(parts[0])
            window = float(parts[1])
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        if not (2 <= limit <= 30) or not (10 <= window <= 3600):
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        _put(api, ctx.chat_id, "mf_limit", limit)
        _put(api, ctx.chat_id, "mf_window_s", window)
        ctx.respond(api.tr(ctx.lang, "set_ok", limit=limit, window=int(window)))

    api.register_event(EVENT_MESSAGE, on_message, priority=190)
    api.register_command("mediaflood", cmd_mediaflood, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("mediaflood",),
                         usage="mediaflood [on|off]")
    api.register_command("setmediaflood", cmd_setmediaflood,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setmediaflood",),
                         usage="setmediaflood <limit 2-30> <window_s 10-3600>")


def on_unload(api) -> None:
    _buckets.clear()
    _last_warn.clear()
