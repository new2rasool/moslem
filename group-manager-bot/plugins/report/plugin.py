"""پلاگین report — سامانهٔ گزارش تخلف اعضا (با محافظت ضد سوءاستفاده).

هر عضو می‌تواند با /report <id> <دلیل> یک گزارش ثبت کند. گزارش‌ها در دفتر
حسابرسی (record_action) ذخیره و به کانال لاگ/مدیران می‌رسند (audit_sink) و
مدیران با /reports آن‌ها را می‌بینند.

محافظت‌ها:
    - گزارش‌دهنده هر ۲ دقیقه فقط یک گزارش (ضد اسپم)
    - سقف ۳ گزارش در ساعت برای هر گزارش‌دهنده
    - گزارش مدیران/کارکنان و خودِ شخص ممنوع است
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_ACTION

PLUGIN_VERSION = "1.0.0"

REPORT_COOLDOWN_S = 120.0
HOURLY_LIMIT = 3
MIN_REASON = 3
MAX_REASON = 200


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
    async def on_report_recorded(ctx) -> None:
        """اعلان داخلی گزارش به کارکنان (در صورت فعال بودن auto-notice)."""
        chat_id = ctx.chat_id
        if chat_id is None:
            return
        if not api.is_enabled(chat_id):
            return
        if ctx.data.get("action") != "report":
            return
        # اطلاع‌رسانی عمومی داخل گروه (آداپتور می‌تواند به کانال خصوصی ببرد)
        if _get(api, chat_id, "report_notice", True):
            target = ctx.data.get("target_user")
            api.host.send_text(
                chat_id,
                api.tr(ctx.lang, "notice", target=target, id=ctx.data.get("id", "")),
            )

    # ── /report ─────────────────────────────────────────────────────
    async def cmd_report(ctx):
        chat_id = ctx.chat_id
        if api.actions is None:
            ctx.respond(api.tr(ctx.lang, "no_storage"))
            return
        reporter = ctx.user_id or 0
        parts = (ctx.args or "").strip().split(maxsplit=1)
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        if not parts[0].lstrip("-").isdigit():
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        target = int(parts[0])
        reason = parts[1].strip()
        if target <= 0 or target == reporter:
            ctx.respond(api.tr(ctx.lang, "no_self"))
            return
        if len(reason) < MIN_REASON or len(reason) > MAX_REASON:
            ctx.respond(api.tr(ctx.lang, "bad_reason", mn=MIN_REASON, mx=MAX_REASON))
            return
        # گزارش کارکنان ممنوع
        if api.access.level(chat_id, target) >= AccessLevel.MOD:
            ctx.respond(api.tr(ctx.lang, "staff_target"))
            return

        now = time.monotonic()
        cd_key = f"report:cd:{chat_id}:{reporter}"
        if api.cache.get(cd_key) is not None:
            ctx.respond(api.tr(ctx.lang, "cooldown", s=int(REPORT_COOLDOWN_S)))
            return
        # سقف ساعتی
        hr_key = f"report:hr:{chat_id}:{reporter}"
        stamps = list(api.cache.get(hr_key) or [])
        stamps = [t for t in stamps if now - t < 3600]
        if len(stamps) >= HOURLY_LIMIT:
            ctx.respond(api.tr(ctx.lang, "hourly_limit", n=HOURLY_LIMIT))
            return

        await api.record_action(chat_id, "report", target, reporter, reason=reason)
        api.cache.set(cd_key, True, ttl_s=REPORT_COOLDOWN_S)
        stamps.append(now)
        api.cache.set(hr_key, stamps, ttl_s=3600)
        ctx.respond(api.tr(ctx.lang, "done", target=target))

    # ── /reports (ادمین) ────────────────────────────────────────────
    async def cmd_reports(ctx):
        if api.actions is None:
            ctx.respond(api.tr(ctx.lang, "no_storage"))
            return
        rows = api.actions.recent(ctx.chat_id, limit=40)
        reports = [r for r in rows if r.get("action") == "report"][:10]
        if not reports:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        lines = [api.tr(ctx.lang, "header", n=len(reports))]
        for r in reports:
            lines.append(
                f"#{r['id']} 🎯 {r['target_user']} ← گزارش‌دهنده {r['by_user']}: "
                f"{r['reason']} [{str(r['created_at'])[:16]}]"
            )
        ctx.respond("\n".join(lines))

    api.register_event(EVENT_ACTION, on_report_recorded, priority=800)
    api.register_command("report", cmd_report, group_only=True,
                         aliases=("report",), usage="report <id> <دلیل>")
    api.register_command("reports", cmd_reports, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("reports",))


def on_unload(api) -> None:
    pass
