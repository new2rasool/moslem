"""پلاگین moderation — سیستم تنبیه و هشدار پلکانی (مدیریت گروه).

یک برش عمودی کامل: ban/kick/mute زماندار + سیستم هشدار با اکشن خودکار + دفتر
حسابرسی (جدول actions) + حالت «دلیل اجباری».

اجرای فیزیکی روی تلگرام (restrict/ban) توسط «آداپتور» انجام می‌شود؛ این پلاگین
تصمیم را می‌گیرد، در دفتر حسابرسی ثبت می‌کند و پیام نتیجه/علت را می‌سازد.
"""

from __future__ import annotations

import re

from bot.domain.duration import DurationError, format_duration, parse_duration
from bot.domain.punishment import PunishmentPolicy
from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

# اکشن‌هایی که «آداپتور اجرای فیزیکی» باید انجام دهد (قرارداد خروجی)
_TARGET_RE = re.compile(r"^-?\d{2,}$")  # آیدی عددی (فقط برای تست/پیاده‌سازی مستقیم)


def _is_id(token: str) -> bool:
    return bool(_TARGET_RE.match(token.strip()))


def _resolve_target(ctx, api) -> tuple[int | None, str | None]:
    """تعیین هدف: اول ریپلای، بعد اولین توکنِ آیدی‌مانند. (نام‌کاربر در آداپتور حل می‌شود)"""
    if ctx.reply_to_user_id:
        return ctx.reply_to_user_id, ""
    for token in ctx.args.split():
        if _is_id(token):
            return int(token), ""
    return None, api.tr(ctx.lang, "err_no_target")


def _split_duration_args(args: str) -> tuple[str | None, str]:
    """اولین توکن اگر مدت‌زمان معتبر بود → (مدت، باقی) وگرنه (None, کل)."""
    parts = args.split(maxsplit=1)
    if not parts:
        return None, ""
    token = parts[0]
    try:
        seconds = parse_duration(token)
    except DurationError:
        return None, args
    return str(seconds), parts[1] if len(parts) > 1 else ""


def register(api) -> None:
    policy = PunishmentPolicy()

    # ── انتخاب اکشن روی هدف با قواعد ایمنی ──────────────────────────
    async def _punish(ctx, action: str, duration_s: int | None = None) -> None:
        """تصمیم‌گیری + ثبت در دفتر حسابرسی + پیام نتیجه. (اجرا با آداپتور)"""
        target_id, err = _resolve_target(ctx, api)
        if err:
            ctx.respond(err)
            return
        assert target_id is not None

        actor_level = api.access.level(ctx.chat_id, ctx.user_id)
        target_level = api.access.level(ctx.chat_id, target_id)
        ok, reason_key = _punish_allowed(
            actor_level, target_level, target_is_bot_owner=api.access.is_bot_owner(target_id)
        )
        if not ok:
            ctx.respond(api.tr(ctx.lang, reason_key))
            return

        reason = ctx.args.strip()
        if not reason and duration_s is not None:
            reason = ""  # در دستورهای زماندار، دلیل اختیاری است

        # حالت «دلیل اجباری»
        strict = _group_setting(api, ctx.chat_id, "strict_reason", False)
        if strict and action in ("ban", "kick", "warn") and not reason:
            ctx.respond(api.tr(ctx.lang, "reason_required"))
            return

        # ثبت در دفتر حسابرسی + انتشار رویداد action_recorded برای کانال لاگ
        await api.record_action(
            ctx.chat_id, action, target_id, ctx.user_id, reason=reason, duration_s=duration_s
        )
        if duration_s:
            ctx.respond(api.tr(ctx.lang, f"done_{action}", name=_name(ctx, api), dur=format_duration(duration_s)))
        else:
            ctx.respond(api.tr(ctx.lang, f"done_{action}", name=_name(ctx, api), dur=""))

    # ── فرمان‌های تنبیه ─────────────────────────────────────────────
    async def cmd_ban(ctx):
        await _punish(ctx, "ban")

    async def cmd_kick(ctx):
        await _punish(ctx, "kick")

    async def cmd_mute(ctx):
        await _punish(ctx, "mute")

    async def cmd_tmute(ctx):
        dur, rest = _split_duration_args(ctx.args)
        if dur is None:
            ctx.respond(api.tr(ctx.lang, "need_duration"))
            return
        ctx.args = rest  # مدت از آرگومان‌ها جدا شد؛ باقی می‌ماند
        await _punish(ctx, "mute", duration_s=int(dur))

    async def cmd_unmute(ctx):
        await _punish(ctx, "unmute")

    async def cmd_unban(ctx):
        await _punish(ctx, "unban")

    async def cmd_recent(ctx):
        if api.actions is None:
            ctx.respond(api.tr(ctx.lang, "no_storage"))
            return
        rows = api.actions.recent(ctx.chat_id, limit=10)
        if not rows:
            ctx.respond(api.tr(ctx.lang, "no_actions"))
            return
        lines = [api.tr(ctx.lang, "recent_header")]
        for r in rows:
            who = r["target_user"]
            actor = r["by_user"]
            extra = format_duration(r["duration_s"]) if r.get("duration_s") else ""
            lines.append(
                f"• {r['action']} → {who} (توسط {actor}) {extra} — {r['reason'] or '—'} [{r['created_at'][:16]}]"
            )
        ctx.respond("\n".join(lines))

    # ── سیستم هشدار ─────────────────────────────────────────────────
    async def cmd_warn(ctx):
        target_id, err = _resolve_target(ctx, api)
        if err:
            ctx.respond(err)
            return
        assert target_id is not None
        if api.warns is None or api.actions is None:
            ctx.respond(api.tr(ctx.lang, "no_storage"))
            return

        actor_level = api.access.level(ctx.chat_id, ctx.user_id)
        target_level = api.access.level(ctx.chat_id, target_id)
        ok, reason_key = _punish_allowed(
            actor_level, target_level, target_is_bot_owner=api.access.is_bot_owner(target_id)
        )
        if not ok:
            ctx.respond(api.tr(ctx.lang, reason_key))
            return

        reason = ctx.args.strip()
        strict = _group_setting(api, ctx.chat_id, "strict_reason", False)
        if strict and not reason:
            ctx.respond(api.tr(ctx.lang, "reason_required"))
            return

        count = api.warns.add(ctx.chat_id, target_id, reason=reason, by_user=ctx.user_id)
        await api.record_action(ctx.chat_id, "warn", target_id, ctx.user_id, reason=reason)
        limit = _group_setting(api, ctx.chat_id, "warn_limit", 3)

        # اکشن خودکار اگر به آستانه رسید
        auto = policy.action_for(count)
        text = api.tr(ctx.lang, "warned", name=_name(ctx, api), count=count, limit=limit)
        if auto is not None:
            action, dur = auto
            api.warns.reset(ctx.chat_id, target_id)
            await api.record_action(ctx.chat_id, f"auto:{action}", target_id, ctx.user_id,
                                    reason="auto after warns", duration_s=dur)
            if dur:
                text += "\n" + api.tr(ctx.lang, "auto_action_timed",
                                      action=action, dur=format_duration(dur))
            else:
                text += "\n" + api.tr(ctx.lang, "auto_action", action=action)
        else:
            nxt = policy.next_level(count)
            if nxt is not None:
                text += "\n" + api.tr(ctx.lang, "next_level", n=nxt)
        ctx.respond(text)

    async def cmd_unwarn(ctx):
        if api.warns is None or api.actions is None:
            ctx.respond(api.tr(ctx.lang, "no_storage"))
            return
        target_id, err = _resolve_target(ctx, api)
        if err:
            ctx.respond(err)
            return
        assert target_id is not None
        remaining = api.warns.remove_last(ctx.chat_id, target_id)
        await api.record_action(ctx.chat_id, "unwarn", target_id, ctx.user_id)
        ctx.respond(api.tr(ctx.lang, "unwarned", name=_name(ctx, api), count=remaining))

    async def cmd_warns(ctx):
        if api.warns is None:
            ctx.respond(api.tr(ctx.lang, "no_storage"))
            return
        target_id, err = _resolve_target(ctx, api)
        if err and ctx.reply_to_user_id is None:
            # نمایش هشدارهای خودِ کاربر
            target_id = ctx.user_id
        elif err:
            ctx.respond(err)
            return
        count = api.warns.count(ctx.chat_id, target_id)
        limit = _group_setting(api, ctx.chat_id, "warn_limit", 3)
        last = api.warns.last_reason(ctx.chat_id, target_id)
        ctx.respond(
            api.tr(ctx.lang, "warns_show", name=_name(ctx, api), count=count, limit=limit,
                   last=last or api.tr(ctx.lang, "none"))
        )

    # ── تنظیمات ─────────────────────────────────────────────────────
    async def cmd_setstrict(ctx):
        val = (ctx.args or "").strip().lower()
        if val in ("on", "روشن", "1", "true"):
            _set_group_setting(api, ctx.chat_id, "strict_reason", True)
            ctx.respond(api.tr(ctx.lang, "strict_on"))
        elif val in ("off", "خاموش", "0", "false"):
            _set_group_setting(api, ctx.chat_id, "strict_reason", False)
            ctx.respond(api.tr(ctx.lang, "strict_off"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage_strict"))

    async def cmd_setwarnlimit(ctx):
        try:
            n = int((ctx.args or "").strip())
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_warnlimit"))
            return
        if not 1 <= n <= 10:
            ctx.respond(api.tr(ctx.lang, "usage_warnlimit"))
            return
        _set_group_setting(api, ctx.chat_id, "warn_limit", n)
        ctx.respond(api.tr(ctx.lang, "warnlimit_set", n=n))

    # ── ثبت فرمان‌ها (گروهی) ────────────────────────────────────────
    api.register_command("ban", cmd_ban, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("ban", "بن"), usage="ban [دلیل] (ریپلای/آیدی)")
    api.register_command("kick", cmd_kick, level=AccessLevel.MOD, group_only=True,
                         aliases=("kick", "اخراج"))
    api.register_command("mute", cmd_mute, level=AccessLevel.MOD, group_only=True,
                         aliases=("mute", "سکوت"))
    api.register_command("tmute", cmd_tmute, level=AccessLevel.MOD, group_only=True,
                         aliases=("tmute", "سکوت موقت"), usage="tmute <مدت> [دلیل]")
    api.register_command("unmute", cmd_unmute, level=AccessLevel.MOD, group_only=True,
                         aliases=("unmute", "رفع سکوت"))
    api.register_command("unban", cmd_unban, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("unban", "آنبن"))
    api.register_command("warn", cmd_warn, level=AccessLevel.MOD, group_only=True,
                         aliases=("warn", "هشدار"), usage="warn [دلیل] (ریپلای)")
    api.register_command("unwarn", cmd_unwarn, level=AccessLevel.MOD, group_only=True,
                         aliases=("unwarn", "حذف هشدار"))
    api.register_command("warns", cmd_warns, group_only=True,
                         aliases=("warns", "هشدارها"), usage="warns [کاربر]")
    api.register_command("recent", cmd_recent, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("recent", "تاریخچه", "گزارش اخیر"))
    api.register_command("setstrict", cmd_setstrict, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setstrict", "دلیل اجباری"))
    api.register_command("setwarnlimit", cmd_setwarnlimit, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setwarnlimit", "حد هشدار"))


# ── کمکی‌ها ──────────────────────────────────────────────────────────
def _punish_allowed(actor_level, target_level, *, target_is_bot_owner: bool) -> tuple[bool, str]:
    """قواعد: مالک ربات مصون؛ فقط سطح بالاتر می‌تواند پایین‌تر را تنبیه کند."""
    from bot.domain.roles import can_punish

    return can_punish(
        actor_level,
        target_level,
        actor_is_bot_owner=False,
        target_is_bot_owner=target_is_bot_owner,
    )


def _name(ctx, api) -> str:
    if ctx.reply_to_user_id and ctx.reply_to_user_name:
        return ctx.reply_to_user_name
    return str(ctx.reply_to_user_id or ctx.user_id)


def _group_setting(api, chat_id, key, default):
    group = api.groups.get(chat_id)
    if group is None:
        return default
    return group.settings.get(key, default)


def _set_group_setting(api, chat_id, key, value) -> None:
    group = api.groups.get(chat_id)
    from bot.repositories.base import Group

    if group is None:
        group = Group(chat_id=chat_id, settings={})
    group.settings[key] = value
    api.groups.upsert(group)
