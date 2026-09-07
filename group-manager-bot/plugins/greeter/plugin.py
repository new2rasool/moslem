"""پلاگین greeter — خوش‌آمد/خداحافظی قابل تنظیم (نمونهٔ رویدادمحور پیشرفته).

به رویدادهای «عضو جدید» و «عضو خارج‌شونده» گوش می‌دهد. متن‌ها را می‌توان با
فرمان‌های گروه (فقط ادمین) بازنویسی و روشن/خاموش کرد؛ همه‌چیز در تنظیمات گروه
ذخیره می‌شود.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED, EVENT_MEMBER_LEFT

PLUGIN_VERSION = "2.0.0"


def _fill(template: str, ctx) -> str:
    """جای‌گذاری متغیرهای ساده — امن (بدون format_map روی متن دلخواه مدیر)."""
    name = str(ctx.data.get("member_name") or ctx.user_name or "")
    username = str(ctx.data.get("member_username") or "")
    chat = str(ctx.data.get("chat_title") or ctx.chat_id or "")
    uid = str(ctx.data.get("member_id") or ctx.user_id or "")
    return (
        template.replace("{name}", name)
        .replace("{username}", username or "—")
        .replace("@{username}", ("@" + username) if username else "—")
        .replace("{chat}", chat)
        .replace("{id}", uid)
        .replace("{count}", str(ctx.data.get("member_count") or "?"))
    )


def register(api) -> None:
    def get_setting(chat_id, key, default):
        group = api.groups.get(chat_id)
        if group is None:
            return default
        return group.settings.get(key, default)

    def set_setting(chat_id, key, value):
        group = api.groups.get(chat_id)
        from bot.repositories.base import Group

        if group is None:
            group = Group(chat_id=chat_id, settings={})
        group.settings[key] = value
        api.groups.upsert(group)

    # ── رویدادها ────────────────────────────────────────────────────
    async def on_member_joined(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None:
            return
        if not api.is_enabled(chat_id):
            return
        if not get_setting(chat_id, "greet_enabled", True):
            return
        text = get_setting(chat_id, "greet_text", api.tr(ctx.lang, "welcome_default"))
        ctx.respond(_fill(text, ctx))

    async def on_member_left(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None:
            return
        if not api.is_enabled(chat_id):
            return
        if not get_setting(chat_id, "goodbye_enabled", False):
            return
        text = get_setting(chat_id, "goodbye_text", api.tr(ctx.lang, "goodbye_default"))
        ctx.respond(_fill(text, ctx))

    # ── فرمان‌ها ────────────────────────────────────────────────────
    async def cmd_setgreet(ctx):
        if not ctx.args:
            ctx.respond(api.tr(ctx.lang, "usage_setgreet"))
            return
        set_setting(ctx.chat_id, "greet_text", ctx.args)
        ctx.respond(api.tr(ctx.lang, "greet_set"))

    async def cmd_setgoodbye(ctx):
        if not ctx.args:
            ctx.respond(api.tr(ctx.lang, "usage_setgoodbye"))
            return
        set_setting(ctx.chat_id, "goodbye_text", ctx.args)
        ctx.respond(api.tr(ctx.lang, "goodbye_set"))

    async def cmd_greet(ctx):
        parts = ctx.args.split()
        if not parts:
            on = get_setting(ctx.chat_id, "greet_enabled", True)
            gb = get_setting(ctx.chat_id, "goodbye_enabled", False)
            state = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            state_gb = api.tr(ctx.lang, "on") if gb else api.tr(ctx.lang, "off")
            preview = _fill(get_setting(ctx.chat_id, "greet_text",
                                        api.tr(ctx.lang, "welcome_default")), ctx)
            ctx.respond(api.tr(ctx.lang, "status", state=state, gb=state_gb, preview=preview))
            return
        if parts[0].lower() in ("on", "روشن"):
            set_setting(ctx.chat_id, "greet_enabled", True)
            ctx.respond(api.tr(ctx.lang, "greet_enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            set_setting(ctx.chat_id, "greet_enabled", False)
            ctx.respond(api.tr(ctx.lang, "greet_disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_goodbye(ctx):
        parts = ctx.args.split()
        if parts and parts[0].lower() in ("on", "روشن"):
            set_setting(ctx.chat_id, "goodbye_enabled", True)
            ctx.respond(api.tr(ctx.lang, "goodbye_on"))
        elif parts and parts[0].lower() in ("off", "خاموش"):
            set_setting(ctx.chat_id, "goodbye_enabled", False)
            ctx.respond(api.tr(ctx.lang, "goodbye_off"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage_goodbye"))

    api.register_event(EVENT_MEMBER_JOINED, on_member_joined, priority=100)
    api.register_event(EVENT_MEMBER_LEFT, on_member_left, priority=100)
    api.register_command("greet", cmd_greet, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("greet", "خوش‌آمد"), usage="greet [on|off]")
    api.register_command("goodbye", cmd_goodbye, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("goodbye", "خداحافظی"), usage="goodbye [on|off]")
    api.register_command("setgreet", cmd_setgreet, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setgreet", "تنظیم خوش‌آمد"),
                         usage="setgreet <متن با {name}>")
    api.register_command("setgoodbye", cmd_setgoodbye, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setgoodbye", "تنظیم خداحافظی"),
                         usage="setgoodbye <متن با {name}>")
