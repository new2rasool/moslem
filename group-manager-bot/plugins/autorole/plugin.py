"""پلاگین autorole — ارتقای خودکار اعضای فعال به «مدیر میانی».

هر پیامِ متنیِ عضوِ عادی شمرده می‌شود؛ پس از رسیدن به آستانه (پیش‌فرض ۳۰
پیام) و در صورت فعال‌بودن، عضو به نقش «mod» ارتقا می‌یابد (یک‌بار؛ با ثبت
auto:promote در دفتر حسابرسی). ضد سوءاستفاده: فقط اعضای USER؛ مهلت خنک‌سازی
بین دو ارتقا.
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel, level_from_db_role
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

DEFAULT_THRESHOLD = 30
DEFAULT_ROLE = "mod"
# chat_id → {user_id: {"count": int, "promoted": bool}}
_counts: dict[int, dict[int, dict]] = {}


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
    async def on_message(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "ar_on", False):
            return
        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        if not raw or raw.startswith("/"):
            return
        if api.access.level(chat_id, user_id) != AccessLevel.USER:
            return
        threshold = int(_get(api, chat_id, "ar_threshold", DEFAULT_THRESHOLD))
        role = str(_get(api, chat_id, "ar_role", DEFAULT_ROLE))
        if role not in ("mod", "admin"):
            return
        bucket = _counts.setdefault(chat_id, {}).setdefault(
            user_id, {"count": 0, "promoted": False})
        bucket["count"] += 1
        if bucket["promoted"] or bucket["count"] < threshold:
            return
        # بررسی نهایی سطح (شاید مدیر دستی ارتقا داده)
        if level_from_db_role(api.roles.get_role(chat_id, user_id)) != AccessLevel.USER:
            bucket["promoted"] = True
            return
        api.roles.set_role(chat_id, user_id, role, by_user=0)
        bucket["promoted"] = True
        name = (ctx.data.get("sender_name") or ctx.user_name or str(user_id))[:24]
        ctx.respond(api.tr(ctx.lang, "promoted", name=name, role=role))
        await api.record_action(chat_id, "auto:promote", user_id, 0,
                                reason=f"autorole پس از {bucket['count']} پیام")

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_autorole(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "ar_on", False)
            t = _get(api, ctx.chat_id, "ar_threshold", DEFAULT_THRESHOLD)
            r = _get(api, ctx.chat_id, "ar_role", DEFAULT_ROLE)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, threshold=t, role=r))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "ar_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "ar_on", False)
            _counts.pop(ctx.chat_id, None)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_setautorole(ctx):
        parts = (ctx.args or "").split()
        if len(parts) < 2 or not parts[0].isdigit():
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        threshold = int(parts[0])
        role = parts[1].lower()
        if not (5 <= threshold <= 1000) or role not in ("mod", "admin"):
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        _put(api, ctx.chat_id, "ar_threshold", threshold)
        _put(api, ctx.chat_id, "ar_role", role)
        _counts.pop(ctx.chat_id, None)
        ctx.respond(api.tr(ctx.lang, "set_ok", threshold=threshold, role=role))

    api.register_event(EVENT_MESSAGE, on_message, priority=7)
    api.register_command("autorole", cmd_autorole, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("autorole",),
                         usage="autorole [on|off]")
    api.register_command("setautorole", cmd_setautorole, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("setautorole",),
                         usage="setautorole <آستانه 5-1000> <mod|admin>")


def on_unload(api) -> None:
    _counts.clear()
