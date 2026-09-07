"""پلاگین reminder — یادآور شخصی.

کاربر در هر چتی «remind <دقیقه> <متن>» ثبت می‌کند؛ on_tick میزبان سررسید را
بررسی و یادآوری را به‌صورت پیام خصوصیِ همان کاربر (chat_id = user_id از طریق
out_sink) می‌فرستد. هر کاربر چند یادآوری با شناسهٔ خود دارد.
"""

from __future__ import annotations

import time

PLUGIN_VERSION = "1.0.0"

MIN_MIN = 1
MAX_MIN = 10080  # یک هفته
MAX_TEXT = 300

# user_id → {id: {"text":…, "due": float}}
_reminders: dict[int, dict[int, dict]] = {}
_counter: dict[int, int] = {}


def register(api) -> None:
    async def cmd_remind(ctx):
        parts = (ctx.args or "").partition(" ")
        minutes_raw = parts[0].strip()
        text = parts[2].strip()
        try:
            minutes = int(minutes_raw)
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        if not (MIN_MIN <= minutes <= MAX_MIN):
            ctx.respond(api.tr(ctx.lang, "bad_min", mn=MIN_MIN, mx=MAX_MIN))
            return
        if not text or len(text) > MAX_TEXT:
            ctx.respond(api.tr(ctx.lang, "bad_text", max=MAX_TEXT))
            return
        user = ctx.user_id
        _counter[user] = _counter.get(user, 0) + 1
        rid = _counter[user]
        _reminders.setdefault(user, {})[rid] = {
            "text": text,
            "due": time.monotonic() + minutes * 60,
        }
        ctx.respond(api.tr(ctx.lang, "set", id=rid, minutes=minutes,
                           text=text[:40]))

    async def cmd_reminders(ctx):
        mine = _reminders.get(ctx.user_id, {})
        if not mine:
            ctx.respond(api.tr(ctx.lang, "none"))
            return
        lines = [api.tr(ctx.lang, "header", n=len(mine))]
        for rid, r in sorted(mine.items()):
            remain = max(0, int((r["due"] - time.monotonic()) / 60))
            lines.append(f"#{rid} — {r['text'][:60]} ({api.tr(ctx.lang, 'in_min', n=remain)})")
        ctx.respond("\n".join(lines))

    async def cmd_rmremind(ctx):
        raw = (ctx.args or "").strip()
        if not raw.isdigit():
            ctx.respond(api.tr(ctx.lang, "usage_del"))
            return
        rid = int(raw)
        mine = _reminders.get(ctx.user_id, {})
        if rid not in mine:
            ctx.respond(api.tr(ctx.lang, "not_found", id=rid))
            return
        del mine[rid]
        ctx.respond(api.tr(ctx.lang, "deleted", id=rid))

    api.register_command("remind", cmd_remind, aliases=("remind", "یادآور"),
                         usage="remind <دقیقه 1-10080> <متن>")
    api.register_command("reminders", cmd_reminders, aliases=("reminders", "یادآوری‌ها"))
    api.register_command("rmremind", cmd_rmremind, aliases=("rmremind",),
                         usage="rmremind <id>")


async def on_tick(api) -> None:
    """ارسال یادآوری‌های سررسیدشده (از میزبان)."""
    now = time.monotonic()
    for user_id, items in list(_reminders.items()):
        for rid, r in list(items.items()):
            if r["due"] > now:
                continue
            items.pop(rid)
            # ارسال به چت خصوصی کاربر (آداپتور user_id را PM می‌داند)
            api.host.send_text(user_id, "⏰ " + r["text"])


def on_unload(api) -> None:
    _reminders.clear()
