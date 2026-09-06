"""پلاگین nameguard — گارد نام تازه‌واردان (نام/یوزرنمِ تبلیغاتی).

هنگام ورود، نام و یوزرنمِ عضو بررسی می‌شود: اگر شامل لینک (دامنه) باشد یا
بیش از ۶۴ نویسه یا شامل ایموجی‌های تبلیغاتیِ شاخص (💰🤑) باشد → اخراج خودکار
با ثبت auto:kick (nameguard) در دفتر. کارکنان معاف‌اند و پیش‌فرض خاموش است.
"""

from __future__ import annotations

from bot.domain.content_policy import has_url
from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED

PLUGIN_VERSION = "1.0.0"

MAX_NAME = 64
BAD_EMOJI = ("💰", "🤑", "💸")


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


def _bad(name: str, username: str) -> str | None:
    """دلیل نام بد؛ یا None اگر سالم باشد."""
    text = (name or "") + " @" + (username or "")
    if has_url(text):
        return "url"
    if len(name or "") > MAX_NAME:
        return "long"
    if any(e in (name or "") for e in BAD_EMOJI):
        return "emoji"
    return None


def register(api) -> None:
    async def on_join(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "nguard_on", False):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        name = str(ctx.data.get("member_name") or ctx.user_name or "")
        username = str(ctx.data.get("member_username") or ctx.user_username or "")
        reason = _bad(name, username)
        if reason is None:
            return
        ctx.respond(api.tr(ctx.lang, "kicked", user=user_id, why=reason))
        ctx.act("kick", user_id=user_id, reason=f"nameguard:{reason}")
        await api.record_action(chat_id, "auto:kick", user_id, 0,
                                reason=f"nameguard:{reason}")

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_nameguard(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "nguard_on", False)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "nguard_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "nguard_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    api.register_event(EVENT_MEMBER_JOINED, on_join, priority=580)
    api.register_command("nameguard", cmd_nameguard, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("nameguard",),
                         usage="nameguard [on|off]")


def on_unload(api) -> None:
    pass
