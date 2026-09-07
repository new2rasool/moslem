"""پلاگین reportops — رسیدگیٔ دکمه‌ای به گزارش‌ها.

مدیر با «handle» آخرین گزارش‌های ثبت‌شده (پلاگین report) را به‌صورت پیام‌هایی
با دکمه‌های «⚠️ هشدار / 👢 اخراج / 🔨 بن / ✅ چشم‌پوشی» می‌بیند و با یک کلیک
رسیدگی می‌کند. هر گزارش فقط یک‌بار قابل رسیدگی است (ضد کلیکِ دوباره) و نتیجه
در دفتر حسابرسی ثبت می‌شود.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

DONE_PREFIX = "reportop:done:"  # کلید کش برای گزارش‌های رسیدگی‌شده
DECISIONS = {"w": "warn", "k": "kick", "b": "ban", "i": "ignore"}
DONE_TTL_S = 86400


def _row_by_id(api, chat_id: int, row_id: int) -> dict | None:
    for r in api.actions.recent(chat_id, limit=100):
        if r.get("id") == row_id:
            return r
    return None


def register(api) -> None:
    # ── فهرست گزارش‌ها با دکمه (ادمین) ──────────────────────────────
    async def cmd_handle(ctx):
        chat_id = ctx.chat_id
        if api.actions is None:
            ctx.respond(api.tr(ctx.lang, "no_storage"))
            return
        rows = api.actions.recent(chat_id, limit=100)
        reports = [r for r in rows if r.get("action") == "report"][:3]
        if not reports:
            ctx.respond(api.tr(ctx.lang, "none"))
            return
        sent = 0
        for r in reports:
            row_id = r["id"]
            if api.cache.get(DONE_PREFIX + str(row_id)):
                continue
            target = r["target_user"]
            reason = (r.get("reason") or "")[:60]
            text = api.tr(ctx.lang, "item", id=row_id, target=target, reason=reason,
                          at=str(r.get("created_at", ""))[:16])
            buttons = [
                [{"text": "⚠️ هشدار", "data": f"reportop:{row_id}:{target}:w"},
                 {"text": "👢 اخراج", "data": f"reportop:{row_id}:{target}:k"}],
                [{"text": "🔨 بن", "data": f"reportop:{row_id}:{target}:b"},
                 {"text": "✅ چشم‌پوشی", "data": f"reportop:{row_id}:{target}:i"}],
            ]
            ctx.respond_buttons(text, buttons)
            sent += 1
        if not sent:
            ctx.respond(api.tr(ctx.lang, "none"))

    # ── کلیک روی یک دکمهٔ رسیدگی ────────────────────────────────────
    async def on_action(ctx) -> None:
        parts = ctx.payload.split(":")
        if len(parts) < 3:
            return
        try:
            row_id, target, decision = int(parts[0]), int(parts[1]), parts[2]
        except ValueError:
            return
        if api.access.level(ctx.chat_id, ctx.user_id) < AccessLevel.ADMIN:
            ctx.respond(api.tr(ctx.lang, "staff_only"))
            return
        key = DONE_PREFIX + str(row_id)
        if api.cache.get(key):
            ctx.respond(api.tr(ctx.lang, "already"))
            return
        api.cache.set(key, True, ttl_s=DONE_TTL_S)
        name = DECISIONS.get(decision)
        if name is None:
            return
        # دلیل اصلیِ گزارش از دفتر بازیابی می‌شود
        reason = ""
        if api.actions is not None:
            row = _row_by_id(api, ctx.chat_id, row_id)
            reason = row.get("reason") or "" if row else ""
        trail = f"report #{row_id}" + (f": {reason[:80]}" if reason else "")
        if name == "ignore":
            ctx.respond(api.tr(ctx.lang, "ignored", id=row_id, target=target))
        else:
            ctx.act(name, user_id=target, reason=f"reportop:{trail}")
            await api.record_action(ctx.chat_id, name, target, ctx.user_id,
                                    reason=f"reportop {trail}")
            labels = {"warn": "هشدار ثبت شد", "kick": "اخراج شد", "ban": "بن شد"}
            ctx.respond(api.tr(ctx.lang, "done", id=row_id, target=target,
                               what=labels[name]))

    api.register_callback("reportop:", on_action)
    api.register_command("handle", cmd_handle, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("handle", "رسیدگی"), usage="handle")


def on_unload(api) -> None:
    pass
