"""پلاگین filters — فیلترهای پاسخ خودکار (Auto-Reply Filters).

مدیر یک «کلیدواژه → پاسخ» تعریف می‌کند؛ هر پیامِ کاربر عادی که شامل آن
کلیدواژه (پس از نرمال‌سازی ضد دورزدن) باشد، پاسخ ذخیره‌شده را می‌گیرد.
مدیران/ربات‌ها معاف‌اند. مفید برای پاسخ به پرسش‌های پرتکرار (قوانین، لینک...).
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel
from bot.domain.text_normalize import normalize_text
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"


def _get(api, chat_id, key, default):
    g = api.groups.get(chat_id)
    return g.settings.get(key, default) if g else default


def _put(api, chat_id, key, value):
    from bot.repositories.base import Group

    g = api.groups.get(chat_id)
    if g is None:
        g = Group(chat_id=chat_id, settings={})
    g.settings[key] = value
    api.groups.upsert(g)


def register(api) -> None:
    async def on_message(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None or ctx.user_id is None or ctx.user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "filters_on", True):
            return
        if api.access.level(chat_id, ctx.user_id) >= AccessLevel.ADMIN:
            return  # مدیران پاسخ فیلتر نمی‌گیرند
        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        if not raw:
            return
        rules = dict(_get(api, chat_id, "filters", {}))
        if not rules:
            return
        norm = normalize_text(raw, leet=True)
        # اول بلندترین کلیدواژه (جلوگیری از برخورد «قوانین» با «قانون»)
        for trigger in sorted(rules, key=len, reverse=True):
            if trigger and trigger in norm:
                ctx.respond(rules[trigger])
                return

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_addfilter(ctx):
        # قالب: trigger => reply
        if "=>" not in ctx.args:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        trigger, _, reply = ctx.args.partition("=>")
        trigger = normalize_text(trigger, leet=True)
        reply = reply.strip()
        if not trigger or not reply:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        rules = dict(_get(api, ctx.chat_id, "filters", {}))
        rules[trigger] = reply
        _put(api, ctx.chat_id, "filters", rules)
        _put(api, ctx.chat_id, "filters_on", True)
        ctx.respond(api.tr(ctx.lang, "added", trigger=trigger, total=len(rules)))

    async def cmd_rmfilter(ctx):
        trigger = normalize_text((ctx.args or "").strip(), leet=True)
        if not trigger:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        rules = dict(_get(api, ctx.chat_id, "filters", {}))
        removed = rules.pop(trigger, None)
        if removed is None:
            ctx.respond(api.tr(ctx.lang, "not_found", trigger=trigger))
            return
        _put(api, ctx.chat_id, "filters", rules)
        ctx.respond(api.tr(ctx.lang, "removed", trigger=trigger, total=len(rules)))

    async def cmd_filters(ctx):
        rules = dict(_get(api, ctx.chat_id, "filters", {}))
        on = _get(api, ctx.chat_id, "filters_on", True)
        st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
        lines = [api.tr(ctx.lang, "header", state=st, n=len(rules))]
        if rules:
            for trigger in sorted(rules):
                lines.append(f"• {trigger}  ←  {rules[trigger][:60]}")
        else:
            lines.append(api.tr(ctx.lang, "empty"))
        ctx.respond("\n".join(lines))

    async def cmd_filterson(ctx):
        parts = ctx.args.split()
        val = parts[0].lower() if parts else ""
        if val in ("on", "روشن"):
            _put(api, ctx.chat_id, "filters_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif val in ("off", "خاموش"):
            _put(api, ctx.chat_id, "filters_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage_onoff"))

    api.register_event(EVENT_MESSAGE, on_message, priority=10)  # بعد از همهٔ ضداسپم‌ها
    api.register_command("addfilter", cmd_addfilter, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("addfilter", "افزودن فیلتر"),
                         usage="addfilter <trigger> => <reply>")
    api.register_command("rmfilter", cmd_rmfilter, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("rmfilter", "حذف فیلتر"))
    api.register_command("filters", cmd_filters, group_only=True,
                         aliases=("filters", "فیلترها"))
    api.register_command("filterson", cmd_filterson, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("filterson", "وضعیت فیلترها"), usage="filterson <on|off>")


def on_unload(api) -> None:
    pass
