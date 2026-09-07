"""پلاگین joinlog — لاگ ورود/خروج اعضا به یک کانال جداگانه.

ورود/خروجِ هر عضو به‌صورت یک خط لاگ به کانالِ تنظیم‌شده با «setjoinlog»
فرستاده می‌شود (عدد مثل -100123… یا 100123…). اگر کانالی تنظیم نشده باشد،
خط به خودِ گروه می‌رود (همان الگوی کانال لاگ حسابرسی). پیش‌فرض خاموش است.

تفاوت با کانال لاگ (audit): این‌جا فقط رویدادهای «عضو وارد شد / خارج شد» ثبت
می‌شود نه اکشن‌های تنبیهی؛ برای پیگیری رفت‌وآمد در گروه‌های بزرگ به‌کار می‌رود.
"""

from __future__ import annotations

from bot.domain.channel import parse_channel_id
from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED, EVENT_MEMBER_LEFT

PLUGIN_VERSION = "1.0.0"


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


def _destination(api, chat_id) -> int | None:
    channel = _get(api, chat_id, "jl_channel", "")
    return parse_channel_id(channel)


def register(api) -> None:
    async def _log(kind: str, ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "jl_on", False):
            return
        data = ctx.data or {}
        uid = data.get("member_id") or ctx.user_id or 0
        name = (data.get("member_name") or ctx.user_name or str(uid))[:40]
        username = data.get("member_username") or ctx.user_username or ""
        title = (data.get("chat_title") or "")[:50]
        who = f"@{username}" if username else str(uid)
        if kind == "joined":
            count = data.get("member_count")
            count_txt = f" 👥 {count}" if count else ""
            text = api.tr(ctx.lang, "joined", name=name, who=who,
                          title=title) + count_txt
        else:
            text = api.tr(ctx.lang, "left", name=name, who=who, title=title)
        dest = _destination(api, chat_id)
        if dest is None:
            dest = chat_id
        api.host.send_text(dest, text)

    async def on_joined(ctx) -> None:
        await _log("joined", ctx)

    async def on_left(ctx) -> None:
        await _log("left", ctx)

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_joinlog(ctx):
        parts = (ctx.args or "").split()
        cmd = parts[0].lower() if parts else ""
        if cmd in ("on", "روشن"):
            _put(api, ctx.chat_id, "jl_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif cmd in ("off", "خاموش"):
            _put(api, ctx.chat_id, "jl_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            on = _get(api, ctx.chat_id, "jl_on", False)
            channel = _get(api, ctx.chat_id, "jl_channel", "")
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st,
                               channel=channel or "—"))

    async def cmd_setjoinlog(ctx):
        raw = (ctx.args or "").strip()
        if not raw or raw in ("off", "-", "حذف"):
            _put(api, ctx.chat_id, "jl_channel", "")
            ctx.respond(api.tr(ctx.lang, "cleared"))
            return
        if parse_channel_id(raw) is None:
            ctx.respond(api.tr(ctx.lang, "bad_channel"))
            return
        _put(api, ctx.chat_id, "jl_channel", raw)
        ctx.respond(api.tr(ctx.lang, "set", channel=raw))

    api.register_event(EVENT_MEMBER_JOINED, on_joined, priority=90)
    api.register_event(EVENT_MEMBER_LEFT, on_left, priority=90)
    api.register_command("joinlog", cmd_joinlog, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("joinlog",),
                         usage="joinlog [on|off]")
    api.register_command("setjoinlog", cmd_setjoinlog,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setjoinlog",),
                         usage="setjoinlog <-100...|off>")


def on_unload(api) -> None:
    pass
