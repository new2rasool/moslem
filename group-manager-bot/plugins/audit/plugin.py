"""پلاگین audit — کانال لاگ و حسابرسی گروه.

شنوندهٔ رویداد داخلی action_recorded است: هر اکشن مهمی که با
`api.record_action` ثبت شود (ban/kick/mute/warn/auto:...) این‌جا به‌صورت یک خط
لاگ استاندارد قالب‌بندی می‌شود. خطوطِ تولیدشده به `host.audit_sink` (که آداپتور
آن را برای ارسال به کانال لاگ گروه تنظیم کرده) تحویل می‌شود.

فرمان‌ها: setlog (ذخیرهٔ آیدی کانال لاگ گروه)، logtest (نمایش پیش‌نمایش قالب).
"""

from __future__ import annotations

from bot.domain.duration import format_duration
from bot.domain.roles import AccessLevel
from bot.registry import EVENT_ACTION

PLUGIN_VERSION = "1.0.0"


def _get(api, chat_id, key, default):
    group = api.groups.get(chat_id)
    if group is None:
        return default
    return group.settings.get(key, default)


def _put(api, chat_id, key, value) -> None:
    from bot.repositories.base import Group

    group = api.groups.get(chat_id)
    if group is None:
        group = Group(chat_id=chat_id, settings={})
    group.settings[key] = value
    api.groups.upsert(group)


# برچسب نمایشی اکشن‌ها برای لاگ
_ACTION_LABEL_FA = {
    "ban": "🔨 بن",
    "unban": "✅ رفع بن",
    "kick": "👢 اخراج",
    "mute": "🔇 سکوت",
    "unmute": "🔊 رفع سکوت",
    "warn": "⚠️ هشدار",
    "unwarn": "♻️ حذف هشدار",
    "promote": "🎖 ارتقا",
    "demote": "📉 عزل",
    "auto:mute": "⚡️ خودکار: سکوت",
    "auto:kick": "⚡️ خودکار: اخراج",
    "auto:ban": "⚡️ خودکار: بن",
    "auto:promote": "⚡️ خودکار: ارتقا",
    "join_approve": "🚪 تأیید ورود",
    "join_deny": "🚪 رد ورود",
    "report": "📮 گزارش",
}


def format_line(api, lang: str, row: dict) -> str:
    """قالب استاندارد یک خط لاگ (برای کانال لاگ)."""
    action = str(row.get("action", ""))
    labels = _ACTION_LABEL_FA if lang == "fa" else {}
    label = labels.get(action, action)
    dur = row.get("duration_s")
    dur_txt = f" ({format_duration(dur)})" if dur else ""
    reason = row.get("reason") or "—"
    target = row.get("target_user")
    by = row.get("by_user")
    at = str(row.get("created_at", ""))[:19]
    return api.tr(
        lang,
        "line",
        label=label,
        dur=dur_txt,
        target=target,
        by=by,
        reason=reason,
        at=at,
    )


def register(api) -> None:
    async def on_action(ctx) -> None:
        row = ctx.data
        if not row.get("chat_id"):
            return
        # فقط اکشن‌های این گروه (rows تکی) — خط قالب‌بندی‌شده بساز
        ctx.respond(format_line(api, ctx.lang, row))

    async def cmd_setlog(ctx):
        val = (ctx.args or "").strip()
        if not val:
            ctx.respond(api.tr(ctx.lang, "usage_setlog"))
            return
        _put(api, ctx.chat_id, "log_channel", val)
        ctx.respond(api.tr(ctx.lang, "log_set", channel=val))

    async def cmd_logtest(ctx):
        sample = {
            "chat_id": ctx.chat_id,
            "action": "ban",
            "target_user": 123456789,
            "by_user": ctx.user_id,
            "reason": api.tr(ctx.lang, "sample_reason"),
            "duration_s": None,
            "created_at": "2026-09-06 12:00:00",
        }
        ctx.respond(format_line(api, ctx.lang, sample))

    async def cmd_log(ctx):
        if api.actions is None:
            ctx.respond(api.tr(ctx.lang, "no_storage"))
            return
        rows = api.actions.recent(ctx.chat_id, limit=5)
        if not rows:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        lines = [api.tr(ctx.lang, "header")]
        for r in reversed(rows):  # قدیمی → جدید برای خوانایی
            lines.append(format_line(api, ctx.lang, r))
        ctx.respond("\n".join(lines))

    api.register_event(EVENT_ACTION, on_action, priority=500)
    api.register_command("setlog", cmd_setlog, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setlog", "تنظیم لاگ"), usage="setlog <@channel|-100...>")
    api.register_command("logtest", cmd_logtest, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("logtest", "آزمایش لاگ"))
    api.register_command("log", cmd_log, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("log", "لاگ", "گزارش"))
