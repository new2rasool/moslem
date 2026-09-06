"""پلاگین antirepeat — جلوگیری از کپی‌پیست/تکرار پیام.

اگر کاربری پیامی با متنِ نرمال‌شدهٔ یکسان (طول ≥ آستانه) را در پنجرهٔ زمانی
معیّن دوباره بفرستد، نسخهٔ دوم حذف و هشدار داده می‌شود (کارکنان معاف‌اند).
هشدار برای هر کاربر هر ۳۰ ثانیه فقط یک‌بار.
"""

from __future__ import annotations

import time
from collections import deque

from bot.domain.roles import AccessLevel
from bot.domain.text_normalize import normalize_text
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

DEFAULT_WINDOW_S = 300.0   # پنج دقیقه
DEFAULT_MIN_LEN = 20
WARN_COOLDOWN_S = 30.0

# chat_id → deque[(user_id, norm, ts)]
_history: dict[int, deque] = {}
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
        if not _get(api, chat_id, "repeat_on", True):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        if not raw:
            return
        min_len = int(_get(api, chat_id, "repeat_min_len", DEFAULT_MIN_LEN))
        if len(raw) < min_len:
            return
        norm = normalize_text(raw, leet=True)
        if len(norm) < min_len:
            return
        window = float(_get(api, chat_id, "repeat_window_s", DEFAULT_WINDOW_S))
        now = time.monotonic()
        bucket = _history.setdefault(chat_id, deque())
        while bucket and now - bucket[0][2] > window:
            bucket.popleft()

        repeated = any(u == user_id and n == norm for u, n, _ in bucket)
        bucket.append((user_id, norm, now))
        if not repeated:
            return
        # حذف + هشدار (با سقف هشدار)
        if now - _last_warn.get((chat_id, user_id), 0.0) < WARN_COOLDOWN_S:
            ctx.act("delete_message", user_id=user_id, reason="repeat")
            return
        _last_warn[(chat_id, user_id)] = now
        ctx.act("delete_message", user_id=user_id, reason="repeat")
        ctx.respond(api.tr(ctx.lang, "repeat_warn", user=user_id))

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_antirepeat(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "repeat_on", True)
            w = _get(api, ctx.chat_id, "repeat_window_s", DEFAULT_WINDOW_S)
            m = _get(api, ctx.chat_id, "repeat_min_len", DEFAULT_MIN_LEN)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, window=int(w), min_len=m))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "repeat_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "repeat_on", False)
            _history.pop(ctx.chat_id, None)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_setrepeat(ctx):
        parts = (ctx.args or "").split()
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        try:
            window = float(parts[0])
            min_len = int(parts[1])
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        if not (10 <= window <= 86400) or not (5 <= min_len <= 100):
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        _put(api, ctx.chat_id, "repeat_window_s", window)
        _put(api, ctx.chat_id, "repeat_min_len", min_len)
        _history.pop(ctx.chat_id, None)
        ctx.respond(api.tr(ctx.lang, "set_ok", window=int(window), min_len=min_len))

    api.register_event(EVENT_MESSAGE, on_message, priority=180)
    api.register_command("antirepeat", cmd_antirepeat, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("antirepeat",),
                         usage="antirepeat [on|off]")
    api.register_command("setrepeat", cmd_setrepeat, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("setrepeat",),
                         usage="setrepeat <window_s 10-86400> <min_len 5-100>")


def on_unload(api) -> None:
    _history.clear()
    _last_warn.clear()
