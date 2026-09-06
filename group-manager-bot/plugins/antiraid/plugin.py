"""پلاگین antiraid — محافظت در برابر موج ورود/حملهٔ گروهی.

- ورودهای پشت‌سرهم را در پنجرهٔ لغزان می‌شمارد (دامنهٔ خالص RaidWindow).
- هنگام عبور از آستانه: هشدار + اکشن «lock_join» (بستن ورود) تا پایان lock_s.
- رهاسازی خودکار پس از پایان قفل با on_tick میزبان.
"""

from __future__ import annotations

import time

from bot.domain.raid import RaidWindow
from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED

PLUGIN_VERSION = "1.0.0"

# پنجره‌های هر گروه: chat_id → RaidWindow (با تنظیمات لحظهٔ ساخت)
_windows: dict[int, RaidWindow] = {}


def _setting(api, chat_id, key, default):
    g = api.groups.get(chat_id)
    return g.settings.get(key, default) if g else default


def _put(api, chat_id, key, value):
    from bot.repositories.base import Group

    g = api.groups.get(chat_id)
    if g is None:
        g = Group(chat_id=chat_id, settings={})
    g.settings[key] = value
    api.groups.upsert(g)


def _window(api, chat_id) -> RaidWindow:
    w = _windows.get(chat_id)
    if w is None:
        w = RaidWindow(
            limit=int(_setting(api, chat_id, "raid_count", 5)),
            window_s=float(_setting(api, chat_id, "raid_window_s", 300)),
            lock_s=float(_setting(api, chat_id, "raid_lock_s", 600)),
        )
        _windows[chat_id] = w
    return w


def register(api) -> None:
    async def on_join(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None:
            return
        if not api.is_enabled(chat_id):
            return
        if not _setting(api, chat_id, "raid_on", True):
            return
        w = _window(api, chat_id)
        # اگر از قبل قفل است فقط اطلاع‌رسانی نکن (رهاسازی با on_tick)
        if w.locked():
            return
        if w.record_join():
            # حمله تشخیص داده شد → قفل + هشدار
            ctx.respond(api.tr(ctx.lang, "raid_detected",
                               secs=int(w.remaining())))
            ctx.act("lock_join", reason="raid", seconds=int(w.lock_s or 600))
            # اقدامات توصیه‌شده به مدیران
            ctx.respond(api.tr(ctx.lang, "advice"))

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_antiraid(ctx):
        parts = ctx.args.split()
        if not parts:
            on = _setting(api, ctx.chat_id, "raid_on", True)
            c = _setting(api, ctx.chat_id, "raid_count", 5)
            w = _setting(api, ctx.chat_id, "raid_window_s", 300)
            lk = _setting(api, ctx.chat_id, "raid_lock_s", 600)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, count=c, window=w, lock=lk))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "raid_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "raid_on", False)
            _windows.pop(ctx.chat_id, None)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_raid(ctx):
        parts = ctx.args.split()
        cmd = parts[0].lower() if parts else ""
        if cmd in ("on", "روشن"):
            w = _window(api, ctx.chat_id)
            w.force_lock()
            ctx.respond(api.tr(ctx.lang, "locked_manual", secs=int(w.remaining())))
            ctx.act("lock_join", reason="raid:manual", seconds=int(w.remaining()))
        elif cmd in ("off", "خاموش"):
            w = _window(api, ctx.chat_id)
            w.unlock()
            _windows.pop(ctx.chat_id, None)
            ctx.respond(api.tr(ctx.lang, "unlocked_manual"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage_raid"))

    async def cmd_raidset(ctx):
        parts = ctx.args.split()
        if len(parts) < 3:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        try:
            count = int(parts[0])
            window = float(parts[1])
            lock = float(parts[2])
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        if not (2 <= count <= 50) or not (10 <= window <= 3600) or not (10 <= lock <= 86400):
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        _put(api, ctx.chat_id, "raid_count", count)
        _put(api, ctx.chat_id, "raid_window_s", window)
        _put(api, ctx.chat_id, "raid_lock_s", lock)
        _windows.pop(ctx.chat_id, None)  # بازسازی با تنظیمات جدید
        ctx.respond(api.tr(ctx.lang, "set_ok", count=count, window=window, lock=lock))

    api.register_event(EVENT_MEMBER_JOINED, on_join, priority=450)
    api.register_command("antiraid", cmd_antiraid, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("antiraid", "ضد راید"), usage="antiraid [on|off]")
    api.register_command("raid", cmd_raid, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("raid", "قفل اضطراری"), usage="raid <on|off>")
    api.register_command("raidset", cmd_raidset, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("raidset", "تنظیم ضد راید"),
                         usage="raidset <count> <window_sec> <lock_sec>")


async def on_tick(api) -> None:
    """رهاسازی خودکار قفل‌های منقضی (از میزبان)."""
    now = time.monotonic()
    for chat_id, w in list(_windows.items()):
        if w.locked(now):
            continue
        api.host.send_text(chat_id, api.tr("fa", "raid_released"))
        _windows.pop(chat_id, None)


def on_unload(api) -> None:
    _windows.clear()
