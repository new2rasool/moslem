"""پلاگین antiflood — ضد سیل پیام (نمونهٔ رویدادمحور پیشرفته).

به رویداد «message» گوش می‌دهد؛ برای هر (گروه،کاربر) پنجرهٔ لغزان نگه می‌دارد و
هنگام عبور از آستانه، هشدار (و اعلان «اکشن شبیه‌سازی‌شده») می‌فرستد. آستانه از
تنظیمات گروه خوانده می‌شود: flood_count / flood_window_s
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

# کلید حافظه: نام پلاگین (شمارنده‌ها درون‌حافظه؛ با ری‌لود پاک می‌شوند)
_buckets: dict[tuple[int, int], deque[float]] = {}  # (chat,user) → زمان پیام‌ها
_last_notice: dict[tuple[int, int], float] = {}

DEFAULT_COUNT = 5
DEFAULT_WINDOW = 3.0


def register(api) -> None:
    async def cmd_flood(ctx):
        parts = ctx.args.split()
        if not parts:
            # نمایش وضعیت
            on = _setting(api, ctx.chat_id, "flood_on", True)
            c = _setting(api, ctx.chat_id, "flood_count", DEFAULT_COUNT)
            w = _setting(api, ctx.chat_id, "flood_window", DEFAULT_WINDOW)
            state = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=state, count=c, window=w))
            return
        if parts[0].lower() in ("on", "روشن"):
            _set(api, ctx.chat_id, "flood_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _set(api, ctx.chat_id, "flood_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_setflood(ctx):
        parts = ctx.args.split()
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        try:
            count = int(parts[0])
            window = float(parts[1])
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        if not (1 <= count <= 30) or not (1 <= window <= 60):
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        _set(api, ctx.chat_id, "flood_count", count)
        _set(api, ctx.chat_id, "flood_window", window)
        ctx.respond(api.tr(ctx.lang, "set_ok", count=count, window=window))

    async def on_message(ctx) -> None:
        """پردازش هر پیام گروه (اجرا توسط آداپتور در فاز ۲)."""
        chat_id = ctx.chat_id
        user_id = ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return  # پیام‌های سرویس/ربات‌ها نادیده گرفته می‌شوند
        if ctx.data.get("skip_flood"):
            return
        if not api.is_enabled(chat_id):
            return  # پلاگین در این گروه خاموش است
        if not _setting(api, chat_id, "flood_on", True):
            return
        # ادمین‌ها و بالاتر معاف‌اند
        level = api.access.level(chat_id, user_id)
        if level >= AccessLevel.MOD:
            return

        limit = _setting(api, chat_id, "flood_count", DEFAULT_COUNT)
        window = float(_setting(api, chat_id, "flood_window", DEFAULT_WINDOW))
        now = time.monotonic()
        key = (chat_id, user_id)

        bucket = _buckets.setdefault(key, deque())
        while bucket and bucket[0] <= now - window:
            bucket.popleft()
        bucket.append(now)
        if len(bucket) > limit:
            # جلوگیری از هشدار تکراری: هر ۱۰ ثانیه یک بار
            if now - _last_notice.get(key, 0.0) > 10.0:
                _last_notice[key] = now
                ctx.respond(api.tr(ctx.lang, "warning", user_id=user_id))
            bucket.popleft()  # شمارنده را در حد مجاز نگه دار

    api.register_event(EVENT_MESSAGE, on_message, priority=200)
    api.register_command("antiflood", cmd_flood, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("antiflood", "ضد سیل"), usage="antiflood [on|off]")
    api.register_command("setflood", cmd_setflood, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setflood", "تنظیم ضد سیل"), usage="setflood <count> <seconds>")


def _setting(api, chat_id, key, default):
    group = api.groups.get(chat_id)
    if group is None:
        return default
    return group.settings.get(key, default)


def _set(api, chat_id, key, value) -> None:
    group = api.groups.get(chat_id)
    from bot.repositories.base import Group

    if group is None:
        group = Group(chat_id=chat_id, settings={})
    group.settings[key] = value
    api.groups.upsert(group)
