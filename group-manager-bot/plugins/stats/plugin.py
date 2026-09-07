"""پلاگین stats — آمار زندهٔ فعالیت گروه.

شمارنده‌های جلسه‌ای (از زمان روشن‌شدن ربات): پیام‌ها بر اساس نوع، ورود/خروج،
کاربرانِ فعال امروز و برترین‌های امروز. /stats نمای کلی فارسی می‌دهد.
همهٔ شمارنده‌ها در حافظه‌اند (ماندگاری با نسخهٔ دیتابیسی بعدی).
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED, EVENT_MEMBER_LEFT, EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

# chat_id → آمار جلسه
_STATS: dict[int, dict] = {}

_TYPE_FA = {
    "text": "متن",
    "photo": "عکس",
    "video": "ویدیو",
    "animation": "گیف",
    "document": "فایل",
    "voice": "ویس",
    "video_note": "پیام تصویری",
    "sticker": "استیکر",
    "forward": "فوروارد",
    "other": "سایر",
}


def _day() -> str:
    from datetime import date

    return date.today().isoformat()


def _bucket(chat_id: int) -> dict:
    day = _day()
    s = _STATS.setdefault(
        chat_id,
        {"messages": 0, "joins": 0, "leaves": 0, "day": day,
         "today": 0, "today_joins": 0, "types": {}, "by_user": {}, "today_top": {}},
    )
    if s["day"] != day:  # گذر از نیمه‌شب → بازنشانی شمارندهٔ «امروز»
        s["day"] = day
        s["today"] = 0
        s["today_joins"] = 0
        s["today_top"] = {}
    return s


def register(api) -> None:
    async def on_message(ctx) -> None:
        chat_id = ctx.chat_id
        user_id = ctx.user_id
        if chat_id is None:
            return
        if not api.is_enabled(chat_id):
            return
        s = _bucket(chat_id)
        s["messages"] += 1
        s["today"] += 1
        ctype = str(ctx.data.get("content_type") or "other")
        ctype = ctype if ctype in _TYPE_FA else "other"
        s["types"][ctype] = s["types"].get(ctype, 0) + 1
        if user_id and user_id > 0:
            name = (str(ctx.data.get("sender_name") or ctx.user_name or user_id))[:24]
            cu = s["by_user"]
            cu[user_id] = {"name": name, "count": cu.get(user_id, {}).get("count", 0) + 1}
            tt = s["today_top"]
            tt[user_id] = {"name": name, "count": tt.get(user_id, {}).get("count", 0) + 1}

    async def on_joined(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None:
            return
        if not api.is_enabled(chat_id):
            return
        s = _bucket(chat_id)
        s["joins"] += 1
        s["today_joins"] += 1

    async def on_left(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None:
            return
        if not api.is_enabled(chat_id):
            return
        s = _bucket(chat_id)
        s["leaves"] += 1

    # ── /stats ──────────────────────────────────────────────────────
    async def cmd_stats(ctx):
        chat_id = ctx.chat_id
        if not api.is_enabled(chat_id):
            return
        s = _bucket(chat_id)
        lines = [api.tr(ctx.lang, "header", chat=chat_id)]
        lines.append(api.tr(ctx.lang, "messages",
                            today=s["today"], total=s["messages"]))
        # خط نوع‌ها (غیرصفر)
        type_line = "، ".join(
            f"{_TYPE_FA[t]} {c}" for t, c in sorted(s["types"].items(),
                                                    key=lambda kv: -kv[1]) if c > 0
        )
        if type_line:
            lines.append("📦 " + type_line)
        lines.append(api.tr(ctx.lang, "joins",
                            today=s["today_joins"], total=s["joins"], leaves=s["leaves"]))
        # برترین‌های امروز
        top = sorted(s["today_top"].items(), key=lambda kv: -kv[1]["count"])[:5]
        if top:
            lines.append(api.tr(ctx.lang, "top_today"))
            for i, (uid, rec) in enumerate(top, start=1):
                lines.append(f"{i}. {rec['name']} — {rec['count']}")
        else:
            lines.append(api.tr(ctx.lang, "no_activity"))
        ctx.respond("\n".join(lines))

    async def cmd_mystats(ctx):
        chat_id = ctx.chat_id
        if not api.is_enabled(chat_id):
            return
        user_id = ctx.user_id
        s = _bucket(chat_id)
        rec = s["by_user"].get(user_id)
        if rec is None:
            ctx.respond(api.tr(ctx.lang, "no_activity_user"))
            return
        ctx.respond(api.tr(ctx.lang, "mystats", name=rec["name"], count=rec["count"]))

    async def cmd_resetstats(ctx):
        _STATS.pop(ctx.chat_id, None)
        ctx.respond(api.tr(ctx.lang, "reset"))

    api.register_event(EVENT_MESSAGE, on_message, priority=5)  # آخرین اولویت‌ها
    api.register_event(EVENT_MEMBER_JOINED, on_joined, priority=5)
    api.register_event(EVENT_MEMBER_LEFT, on_left, priority=5)
    api.register_command("stats", cmd_stats, group_only=True, aliases=("stats", "آمار"))
    api.register_command("mystats", cmd_mystats, group_only=True, aliases=("mystats", "آمار من"))
    api.register_command("resetstats", cmd_resetstats, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("resetstats", "صفر کردن آمار"))


def on_unload(api) -> None:
    _STATS.clear()
