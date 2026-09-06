"""پلاگین botprotect — کنترل ورود ربات‌ها به گروه.

ربات‌هایی که توسط مدیران به گروه اضافه می‌شوند در رویداد member_joined با
پرچم member_bot می‌آیند. وقتی botprotect روشن باشد، رباتِ ناآشنا بلافاصله
اخراج/بن می‌شود (پیش‌فرض ban) و ربات‌های موجود در لیست سفیدِ گروه معاف‌اند.

روی رویداد member_joined با اولویت ۵۹۰ اجرا می‌شود (بعد از gban و قبل از
nameguard/joinapprove/captcha) تا ربات مشکوک زودتر از چالش‌های ورود حذف شود.
کارکنان (mod به بالا) و لیست سفید بررسی نمی‌شوند؛ هدفِ بن هرگز کارکن نیست.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED

PLUGIN_VERSION = "1.0.0"

MAX_ALLOW = 30  # سقف لیست سفید


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


def _allow_list(api, chat_id) -> list[int]:
    return [int(x) for x in _get(api, chat_id, "bp_allow", []) or []]


def _save_allow(api, chat_id, allow: list[int]) -> None:
    _put(api, chat_id, "bp_allow", allow)


def register(api) -> None:
    async def on_join(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "bp_on", False):
            return
        data = ctx.data or {}
        if not data.get("member_bot"):
            return
        if user_id in _allow_list(api, chat_id):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        mode = _get(api, chat_id, "bp_mode", "ban")
        kind = "auto:ban" if mode == "ban" else "auto:kick"
        name = (data.get("member_name") or ctx.user_name or str(user_id))[:40]
        ctx.respond(api.tr(ctx.lang, "blocked", name=name, user=user_id,
                           mode=mode))
        ctx.act(mode, user_id=user_id, reason="botprotect")
        await api.record_action(chat_id, kind, user_id, 0,
                                reason="botprotect")

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_botprotect(ctx):
        chat_id = ctx.chat_id
        parts = (ctx.args or "").split()
        cmd = parts[0].lower() if parts else ""
        if cmd in ("on", "روشن"):
            _put(api, chat_id, "bp_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif cmd in ("off", "خاموش"):
            _put(api, chat_id, "bp_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        elif cmd in ("ban", "بن"):
            _put(api, chat_id, "bp_mode", "ban")
            ctx.respond(api.tr(ctx.lang, "mode_set", mode="ban"))
        elif cmd in ("kick", "اخراج"):
            _put(api, chat_id, "bp_mode", "kick")
            ctx.respond(api.tr(ctx.lang, "mode_set", mode="kick"))
        elif cmd in ("allow", "اجازه") and len(parts) > 1 and \
                parts[1].lstrip("-").isdigit():
            allow = _allow_list(api, chat_id)
            uid = int(parts[1])
            if uid not in allow:
                allow.append(uid)
                _save_allow(api, chat_id, allow)
            ctx.respond(api.tr(ctx.lang, "allowed", user=uid))
        elif cmd in ("deny", "حذف") and len(parts) > 1 and \
                parts[1].lstrip("-").isdigit():
            allow = _allow_list(api, chat_id)
            uid = int(parts[1])
            if uid in allow:
                allow.remove(uid)
                _save_allow(api, chat_id, allow)
            ctx.respond(api.tr(ctx.lang, "denied", user=uid))
        elif cmd in ("list", "فهرست"):
            allow = _allow_list(api, chat_id)
            if not allow:
                ctx.respond(api.tr(ctx.lang, "empty_allow"))
                return
            ctx.respond(api.tr(ctx.lang, "allow_list",
                               ids="، ".join(str(x) for x in allow)))
        else:
            on = _get(api, chat_id, "bp_on", False)
            mode = _get(api, chat_id, "bp_mode", "ban")
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, mode=mode,
                               n=len(_allow_list(api, chat_id))))

    api.register_event(EVENT_MEMBER_JOINED, on_join, priority=590)
    api.register_command("botprotect", cmd_botprotect,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("botprotect", "ضد ربات"),
                         usage="botprotect [on|off|ban|kick|allow <id>|deny <id>|list]")


def on_unload(api) -> None:
    pass
