"""پلاگین locks — قفل‌های محتوای گروه (لینک/فوروارد/رسانه).

سیاست خالص در `domain/content_policy`؛ اجرا در این پلاگین:
- هر پیام (رویداد message) بررسی و در صورت نقض، «اکشن ساختاریافته» صادر می‌شود
  (delete → adapter حذف می‌کند؛ warn → حذف + پیام؛ notify → فقط اعلان).
- مدیران و بالاتر معاف‌اند. تنظیمات هر گروه: locks (آیتم→اکشن)، wl_domains.
"""

from __future__ import annotations

from bot.domain.content_policy import LOCKABLE, VALID_ACTIONS, check_message
from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"


def _get(api, chat_id, key, default):
    group = api.groups.get(chat_id)
    if group is None:
        return default
    return group.settings.get(key, default)


def _put(api, chat_id, key, value) -> None:
    from bot.repositories.base import Group

    group = api.groups.get(chat_id)
    if group is None:
        group = Group(chat_id=chat_id, settings={})
    group.settings[key] = value
    api.groups.upsert(group)


def register(api) -> None:
    # ── رویداد پیام: اعمال قفل‌ها ───────────────────────────────────
    async def on_message(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None or ctx.user_id is None or ctx.user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "locks_on", True):
            return
        level = api.access.level(chat_id, ctx.user_id)
        if level >= AccessLevel.ADMIN:
            return

        locks = _get(api, chat_id, "locks", {})
        if not locks:
            return
        content_type = str(ctx.data.get("content_type") or ctx.data.get("media") or "text")
        text = str(ctx.data.get("text") or ctx.data.get("caption") or "")
        is_forward = bool(ctx.data.get("is_forward"))
        whitelist = list(_get(api, chat_id, "wl_domains", []))

        hit = check_message(
            content_type=content_type,
            text=text,
            is_forward=is_forward,
            locks=locks,
            url_whitelist=whitelist,
        )
        if hit is None:
            return
        mode = locks.get(hit, "delete")

        # اکشن ساختاریافته برای آداپتور (حذف پیامِ تخلف‌زننده)
        ctx.act("delete_message", reason=f"lock:{hit}", user_id=ctx.user_id)
        if mode == "warn":
            ctx.respond(api.tr(ctx.lang, "violation_warn", item=hit, user=ctx.user_id))
        elif mode == "notify":
            ctx.respond(api.tr(ctx.lang, "violation_notify", item=hit, user=ctx.user_id))
        # mode=delete → فقط حذف بی‌صدا (بدون پیام)

    # ── فرمان‌ها ────────────────────────────────────────────────────
    async def cmd_lock(ctx):
        parts = ctx.args.split()
        if not parts or parts[0].lower() not in LOCKABLE:
            ctx.respond(api.tr(ctx.lang, "usage_lock"))
            return
        item = parts[0].lower()
        mode = "delete"
        if len(parts) > 1 and parts[1].lower() in VALID_ACTIONS:
            mode = parts[1].lower()
        elif len(parts) > 1:
            ctx.respond(api.tr(ctx.lang, "bad_mode", mode=parts[1]))
            return
        locks = dict(_get(api, ctx.chat_id, "locks", {}))
        locks[item] = mode
        _put(api, ctx.chat_id, "locks", locks)
        _put(api, ctx.chat_id, "locks_on", True)
        ctx.respond(api.tr(ctx.lang, "locked", item=item, mode=mode))

    async def cmd_unlock(ctx):
        parts = ctx.args.split()
        if not parts or parts[0].lower() not in LOCKABLE:
            ctx.respond(api.tr(ctx.lang, "usage_lock"))
            return
        item = parts[0].lower()
        locks = dict(_get(api, ctx.chat_id, "locks", {}))
        locks.pop(item, None)
        _put(api, ctx.chat_id, "locks", locks)
        ctx.respond(api.tr(ctx.lang, "unlocked", item=item))

    async def cmd_locks(ctx):
        locks = _get(api, ctx.chat_id, "locks", {})
        on = _get(api, ctx.chat_id, "locks_on", True)
        wl = _get(api, ctx.chat_id, "wl_domains", [])
        state = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
        lines = [api.tr(ctx.lang, "status_header", state=state)]
        if locks:
            for item in sorted(locks):
                lines.append(f"🔒 {item} — {locks[item]}")
        else:
            lines.append(api.tr(ctx.lang, "no_locks"))
        if wl:
            lines.append(api.tr(ctx.lang, "whitelist_show", domains="، ".join(wl)))
        ctx.respond("\n".join(lines))

    async def cmd_locks_onoff(ctx):
        parts = ctx.args.split()
        val = parts[0].lower() if parts else ""
        if val in ("on", "روشن"):
            _put(api, ctx.chat_id, "locks_on", True)
            ctx.respond(api.tr(ctx.lang, "locks_enabled"))
        elif val in ("off", "خاموش"):
            _put(api, ctx.chat_id, "locks_on", False)
            ctx.respond(api.tr(ctx.lang, "locks_disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage_onoff"))

    async def cmd_wl_add(ctx):
        domains = [d.strip().lower().lstrip(".") for d in ctx.args.split() if d.strip()]
        if not domains:
            ctx.respond(api.tr(ctx.lang, "usage_wl"))
            return
        wl = set(_get(api, ctx.chat_id, "wl_domains", []))
        before = len(wl)
        wl.update(domains)
        _put(api, ctx.chat_id, "wl_domains", sorted(wl))
        ctx.respond(api.tr(ctx.lang, "wl_added", n=len(wl) - before, total=len(wl)))

    async def cmd_wl_rm(ctx):
        domains = [d.strip().lower().lstrip(".") for d in ctx.args.split() if d.strip()]
        if not domains:
            ctx.respond(api.tr(ctx.lang, "usage_wl"))
            return
        wl = set(_get(api, ctx.chat_id, "wl_domains", []))
        wl.difference_update(domains)
        _put(api, ctx.chat_id, "wl_domains", sorted(wl))
        ctx.respond(api.tr(ctx.lang, "wl_removed", total=len(wl)))

    api.register_event(EVENT_MESSAGE, on_message, priority=300)
    api.register_command("lock", cmd_lock, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("lock", "قفل"),
                         usage=f"lock <{', '.join(sorted(LOCKABLE))}> [delete|warn|notify]")
    api.register_command("unlock", cmd_unlock, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("unlock", "آزاد کردن"))
    api.register_command("locks", cmd_locks, group_only=True,
                         aliases=("locks", "قفل‌ها"))
    api.register_command("lockson", cmd_locks_onoff, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("lockson", "فعال‌سازی قفل‌ها"))
    api.register_command("lockaddwl", cmd_wl_add, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("lockaddwl", "افزودن دامنه مجاز"))
    api.register_command("lockrmwl", cmd_wl_rm, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("lockrmwl", "حذف دامنه مجاز"))
