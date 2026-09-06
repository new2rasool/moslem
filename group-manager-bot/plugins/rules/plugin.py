"""پلاگین rules — قوانین گروه.

مدیر متن قوانین را ذخیره می‌کند (/setrules)؛ هر عضو با /rules آن را می‌بیند و
هر تازه‌واردی به‌صورت خودکار (یک‌بار) هنگام ورود دریافتش می‌کند.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED

PLUGIN_VERSION = "1.0.0"

MAX_RULES_LEN = 3500


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


def _format(rules: str) -> str:
    """تبدیل متن خام به فهرست شماره‌دار تمیز (خطوطِ خالی/تکراری حذف)."""
    lines = []
    seen = set()
    for raw in (rules or "").splitlines():
        line = raw.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        lines.append(line)
    if not lines:
        return ""
    return "\n".join(f"{i}. {ln}" for i, ln in enumerate(lines, start=1))


def register(api) -> None:
    # ── ارسال خودکار به تازه‌وارد ───────────────────────────────────
    async def on_join(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "rules_on", True):
            return
        text = _format(_get(api, chat_id, "rules_text", ""))
        if not text:
            return
        ctx.respond(api.tr(ctx.lang, "welcome_rules", user=user_id) + "\n" + text)

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_rules(ctx):
        text = _format(_get(api, ctx.chat_id, "rules_text", ""))
        if not text:
            ctx.respond(api.tr(ctx.lang, "none"))
            return
        ctx.respond("📜 " + text)

    async def cmd_setrules(ctx):
        # جداکنندهٔ «|» برای چندبندی‌کردن (خطوطِ واقعی در فرمان یک‌خطی ممکن نیست)
        text = (ctx.args or "").strip().replace(" | ", "\n")
        if not text:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        if len(text) > MAX_RULES_LEN:
            ctx.respond(api.tr(ctx.lang, "too_long", max=MAX_RULES_LEN))
            return
        _put(api, ctx.chat_id, "rules_text", text)
        _put(api, ctx.chat_id, "rules_on", True)
        ctx.respond(api.tr(ctx.lang, "saved", n=len(_format(text).splitlines())))

    async def cmd_delrules(ctx):
        _put(api, ctx.chat_id, "rules_text", "")
        ctx.respond(api.tr(ctx.lang, "deleted"))

    async def cmd_ruleson(ctx):
        parts = (ctx.args or "").split()
        val = parts[0].lower() if parts else ""
        if val in ("on", "روشن"):
            _put(api, ctx.chat_id, "rules_on", True)
            ctx.respond(api.tr(ctx.lang, "auto_on"))
        elif val in ("off", "خاموش"):
            _put(api, ctx.chat_id, "rules_on", False)
            ctx.respond(api.tr(ctx.lang, "auto_off"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage_onoff"))

    api.register_event(EVENT_MEMBER_JOINED, on_join, priority=300)
    api.register_command("rules", cmd_rules, group_only=True,
                         aliases=("rules", "قوانین"))
    api.register_command("setrules", cmd_setrules, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("setrules",),
                         usage="setrules <متن قوانین>")
    api.register_command("delrules", cmd_delrules, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("delrules",))
    api.register_command("ruleson", cmd_ruleson, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("ruleson",),
                         usage="ruleson <on|off>")


def on_unload(api) -> None:
    pass
