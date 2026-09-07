"""پلاگین karma — امتیاز قدردانی بین اعضای گروه.

هر عضو عادی می‌تواند با «karma <id>» یا ریپلایِ «karma» به یک عضوِ عادیِ دیگر
یک امتیاز «تشکر» بدهد. ضد سوءاستفاده: به خودتان نه، به کارکنان نه، به هر
شخص از هر دهنده یک‌بار در ۲۴ ساعت، و فاصلهٔ ۵ ثانیه بین دو تقدیرِ یک دهنده.

امتیازها در تنظیمات گروه (کلید karma_map) با نام آخرِ هر کاربر ذخیره می‌شود؛
«karmatop» برترین‌ها و «karmareset» (ادمین) صفرکنندهٔ همه است.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

DAY_S = 86400
COOL_S = 5
MAX_TOP = 20

_MEDALS = ("🥇", "🥈", "🥉")


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


def _map(api, chat_id) -> dict[str, dict]:
    return dict(_get(api, chat_id, "karma_map", {}) or {})


def _score(api, chat_id, user_id: int) -> tuple[int, str] | None:
    entry = _map(api, chat_id).get(str(user_id))
    if entry is None:
        return None
    return int(entry.get("points", 0)), str(entry.get("name", ""))


def register(api) -> None:
    async def cmd_karma(ctx):
        chat_id = ctx.chat_id
        raw = (ctx.args or "").strip()
        # ── نمایش امتیاز خود ──
        if not raw and ctx.reply_to_user_id is None:
            found = _score(api, chat_id, ctx.user_id)
            if found is None:
                ctx.respond(api.tr(ctx.lang, "no_self", user=ctx.user_id))
                return
            points, name = found
            ctx.respond(api.tr(ctx.lang, "self_score", user=ctx.user_id,
                               name=name, n=points))
            return

        # ── تعیین هدف: ریپلای یا آیدی صریح ──
        target = ctx.reply_to_user_id
        target_name = ctx.reply_to_user_name or ""
        if target is None:
            if not raw.lstrip("-").isdigit():
                ctx.respond(api.tr(ctx.lang, "usage"))
                return
            target = int(raw)
            if target > 0:
                known = _map(api, chat_id).get(str(target))
                if known:
                    target_name = str(known.get("name", ""))
        if target is None or target <= 0 or target == ctx.user_id:
            ctx.respond(api.tr(ctx.lang, "no_self_target"))
            return
        if api.access.level(chat_id, target) >= AccessLevel.MOD:
            ctx.respond(api.tr(ctx.lang, "staff_target"))
            return
        if api.access.level(chat_id, ctx.user_id) >= AccessLevel.MOD:
            # مدیران برای قدردانی از دیگران امتیاز نمی‌دهند (جلوگیری از سوءاستفاده)
            ctx.respond(api.tr(ctx.lang, "staff_giver"))
            return

        cool_key = f"karma:cool:{chat_id}:{ctx.user_id}"
        if api.cache.get(cool_key):
            ctx.respond(api.tr(ctx.lang, "cooldown", s=COOL_S))
            return
        given_key = f"karma:given:{chat_id}:{ctx.user_id}:{target}"
        if api.cache.get(given_key):
            ctx.respond(api.tr(ctx.lang, "already"))
            return
        api.cache.set(cool_key, 1, ttl_s=COOL_S)
        api.cache.set(given_key, 1, ttl_s=DAY_S)

        kmap = _map(api, chat_id)
        entry = kmap.get(str(target)) or {"name": "", "points": 0}
        if not target_name:
            target_name = str(entry.get("name") or target)
        entry["name"] = target_name
        entry["points"] = int(entry.get("points", 0)) + 1
        kmap[str(target)] = entry
        _put(api, chat_id, "karma_map", kmap)
        ctx.respond(api.tr(ctx.lang, "gave", user=target, name=target_name,
                           n=int(entry["points"])))

    # ── برترین‌ها ────────────────────────────────────────────────────
    async def cmd_karmatop(ctx):
        chat_id = ctx.chat_id
        kmap = _map(api, chat_id)
        if not kmap:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        raw = (ctx.args or "").strip()
        n = 10
        if raw.isdigit():
            n = min(max(int(raw), 1), MAX_TOP)
        rows = sorted(kmap.items(),
                      key=lambda kv: int(kv[1].get("points", 0)),
                      reverse=True)[:n]
        lines = [api.tr(ctx.lang, "top_header")]
        for rank, (uid, entry) in enumerate(rows, start=1):
            name = str(entry.get("name") or uid)
            medal = _MEDALS[rank - 1] if rank <= 3 else f"{rank}."
            lines.append(f"{medal} {name} — {int(entry.get('points', 0))}")
        ctx.respond("\n".join(lines))

    # ── صفر کردن (ادمین) ────────────────────────────────────────────
    async def cmd_karmareset(ctx):
        _put(api, ctx.chat_id, "karma_map", {})
        ctx.respond(api.tr(ctx.lang, "reset"))

    api.register_command("karma", cmd_karma, group_only=True,
                         aliases=("karma", "تشکر", "قدردانی"),
                         usage="karma [id] (یا ریپلای)")
    api.register_command("karmatop", cmd_karmatop, group_only=True,
                         aliases=("karmatop",),
                         usage="karmatop [تعداد]")
    api.register_command("karmareset", cmd_karmareset,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("karmareset",),
                         usage="karmareset")


def on_unload(api) -> None:
    pass
