"""پلاگین automod — موتور تشدید خودکار مجازات (رفتارمحور، بسیار پیشرفته).

به رویداد داخلی action_recorded گوش می‌دهد و «الگوی رفتاریِ» هدف را در دفتر
حسابرسی تحلیل می‌کند (دامنهٔ خالص escalation.py):
    - تکرار اخراج (پیش‌فرض ۲ بار در ۸ اکشنِ اخیر) → بن خودکار
    - سکوت‌های پیاپی (پیش‌فرض ۳ بار) → بن خودکار
مدیران/کارکنان معاف‌اند؛ ردیف‌هایِ خودِ ربات شمارش نمی‌شوند (ضد حلقه)؛
پس از بن، هدف تا وقتی «ردیف بن» دارد دوباره تشدید نمی‌شود. پیش‌فرض خاموش است.
"""

from __future__ import annotations

import time

from bot.domain.escalation import STOP_ACTIONS, escalate
from bot.domain.roles import AccessLevel
from bot.registry import EVENT_ACTION

PLUGIN_VERSION = "1.0.0"

DEFAULT_KICK_BAN = 2
DEFAULT_MUTE_BAN = 3
_ACT_COOLDOWN_S = 90.0  # بین دو اقدام خودکار روی یک هدف
_last_act: dict[tuple[int, int], float] = {}


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
    async def on_action(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None or api.actions is None:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "automod_on", False):
            return
        row = ctx.data
        action = str(row.get("action") or "")
        target = row.get("target_user") or 0
        actor = row.get("by_user") or 0
        if target <= 0 or actor <= 0:  # فقط واکنش به اکشن‌هایِ انسانی
            return
        if action in STOP_ACTIONS:
            return
        # کارکنان گروه را هرگز خودکار جریمه نکن
        if api.access.level(chat_id, target) >= AccessLevel.MOD:
            return

        # تحلیل الگو
        rows = api.actions.recent(chat_id, limit=16)
        decision = escalate(
            rows,
            target=target,
            kick_ban=int(_get(api, chat_id, "automod_kick_ban", DEFAULT_KICK_BAN)),
            mute_ban=int(_get(api, chat_id, "automod_mute_ban", DEFAULT_MUTE_BAN)),
        )
        if decision is None:
            return

        # ضد حلقه: بین دو اقدام خودکار روی یک هدف فاصله بگذار
        now = time.monotonic()
        key = (chat_id, target)
        if now - _last_act.get(key, 0.0) < _ACT_COOLDOWN_S:
            return
        _last_act[key] = now

        reason = api.tr(ctx.lang, "reason", action=action, target=target)
        # ۱) اجرای فیزیکی بن (آداپتور)
        api.host.push_action(chat_id, {"type": "ban", "user_id": target,
                                       "reason": f"automod:{action}"})
        # ۲) اطلاع‌رسانی به گروه
        api.host.send_text(chat_id, reason)
        # ۳) ثبت در دفتر حسابرسی + کانال لاگ
        await api.record_action(chat_id, "auto:ban", target, 0, reason=f"automod:{action}")

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_automod(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "automod_on", False)
            kb = _get(api, ctx.chat_id, "automod_kick_ban", DEFAULT_KICK_BAN)
            mb = _get(api, ctx.chat_id, "automod_mute_ban", DEFAULT_MUTE_BAN)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, kick=kb, mute=mb))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "automod_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "automod_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_automodset(ctx):
        parts = (ctx.args or "").split()
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        try:
            kick_ban = int(parts[0])
            mute_ban = int(parts[1])
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        if not (1 <= kick_ban <= 6) or not (1 <= mute_ban <= 10):
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        _put(api, ctx.chat_id, "automod_kick_ban", kick_ban)
        _put(api, ctx.chat_id, "automod_mute_ban", mute_ban)
        ctx.respond(api.tr(ctx.lang, "set_ok", kick=kick_ban, mute=mute_ban))

    api.register_event(EVENT_ACTION, on_action, priority=900)
    api.register_command("automod", cmd_automod, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("automod", "مدیریت خودکار"), usage="automod [on|off]")
    api.register_command("automodset", cmd_automodset, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("automodset", "تنظیم مدیریت خودکار"),
                         usage="automodset <kick_ban 1-6> <mute_ban 1-10>")


def on_unload(api) -> None:
    _last_act.clear()
