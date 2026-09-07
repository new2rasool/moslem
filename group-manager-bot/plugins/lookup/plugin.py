"""پلاگین lookup — کارت تشخیص کاربر (نقش، اخطارها، سابقه، گزارش‌ها، بن سراسری).

/lookup بدون آرگومان → کارت خودِ کاربر؛ /lookup <id> → کارت همان کاربر.
کارت شامل: سطح/نقش، تعداد و آخرین دلیل اخطار، شمار اکشن‌های تنبیهی اخیر
(kick/mute/ban)، شمار گزارش‌های ثبت‌شده علیه کاربر، و وضعیت بن سراسری.
"""

from __future__ import annotations

from bot.domain.roles import LEVEL_LABELS_EN, LEVEL_LABELS_FA

PLUGIN_VERSION = "1.0.0"

GBAN_KEY = "gban:list"  # قرارداد اشتراک با پلاگین gban
PUNISH_ACTIONS = {"kick", "mute", "ban", "warn", "auto:kick", "auto:mute", "auto:ban"}


def register(api) -> None:
    async def cmd_lookup(ctx):
        chat_id = ctx.chat_id
        if api.warns is None or api.actions is None:
            ctx.respond(api.tr(ctx.lang, "no_storage"))
            return
        target = (ctx.args or "").strip()
        if target.lstrip("-").isdigit():
            user_id = int(target)
            if user_id <= 0:
                ctx.respond(api.tr(ctx.lang, "usage"))
                return
        elif target:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        else:
            user_id = ctx.user_id  # بدون آرگومان → خودم

        labels = LEVEL_LABELS_FA if ctx.lang == "fa" else LEVEL_LABELS_EN
        level = api.access.level(chat_id, user_id)
        lines = [api.tr(ctx.lang, "header", id=user_id)]
        lines.append(f"🏷 {api.tr(ctx.lang, 'role')}: {labels.get(level, level.name)}")

        # اخطارها
        warns = api.warns.count(chat_id, user_id)
        wline = api.tr(ctx.lang, "warns", n=warns)
        if warns:
            wline += " — " + api.tr(ctx.lang, "last_reason") + ": " + \
                (api.warns.last_reason(chat_id, user_id) or "—")
        lines.append(wline)

        # سابقهٔ تنبیهی اخیر (۳۰ اکشن آخر دفتر، فقط همین هدف)
        rows = api.actions.recent(chat_id, limit=30)
        mine = [r for r in rows if r.get("target_user") == user_id]
        punish = [r for r in mine if r.get("action") in PUNISH_ACTIONS]
        reports = [r for r in mine if r.get("action") == "report"]
        if punish:
            kinds = {}
            for r in punish:
                kinds[r["action"]] = kinds.get(r["action"], 0) + 1
            summary = "، ".join(f"{k} {v}" for k, v in sorted(kinds.items()))
            lines.append("⚠️ " + api.tr(ctx.lang, "punish_history") + ": " + summary)
        else:
            lines.append("✅ " + api.tr(ctx.lang, "clean_history"))
        if reports:
            lines.append("📮 " + api.tr(ctx.lang, "reports", n=len(reports)))

        # بن سراسری
        gbanned = dict(api.cache.get(GBAN_KEY) or {})
        entry = gbanned.get(user_id)
        if entry:
            lines.append("🚫 " + api.tr(ctx.lang, "gbanned", reason=entry.get("reason") or "—"))
        ctx.respond("\n".join(lines))

    api.register_command("lookup", cmd_lookup, group_only=True,
                         aliases=("lookup",), usage="lookup [id]")


def on_unload(api) -> None:
    pass
