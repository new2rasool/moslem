"""پلاگین levels — سیستم تجربه/سطح/رتبه‌بندی اعضا.

- به هر پیامِ متنیِ عضوِ عادی، امتیاز تعلق می‌گیرد (طبق domain/levels).
- «مهلت خنک‌سازی» بین دو دریافت امتیاز (پیش‌فرض ۳۰ ثانیه) ضد اسپم است.
- صعود سطح در گروه اعلام می‌شود؛ /rank وضعیت خود/دیگری، /top ده نفر برتر.
- آمار در حافظه نگه داشته می‌شود (برای نسخهٔ بعدی: ماندگاری در دیتابیس).
"""

from __future__ import annotations

from bot.domain.levels import level_from_xp, progress, xp_for_level, xp_gain, xp_gain_media, xp_to_next_level
from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

DEFAULT_COOLDOWN_S = 30
MAX_NAME = 24

# chat_id → user_id → {"xp": int, "name": str, "last": float(زمان)}
_xp: dict[int, dict[int, dict]] = {}


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


def _board(chat_id: int) -> dict[int, dict]:
    return _xp.setdefault(chat_id, {})


def register(api) -> None:
    # ── شمارندهٔ امتیاز ─────────────────────────────────────────────
    async def on_message(ctx) -> None:
        chat_id = ctx.chat_id
        user_id = ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "levels_on", True):
            return
        # مدیران و بالاتر رتبه نمی‌گیرند
        if api.access.level(chat_id, user_id) >= AccessLevel.ADMIN:
            return
        import time

        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        ctype = str(ctx.data.get("content_type") or "text")
        if ctype in ("photo", "video", "animation", "document", "voice", "video_note", "sticker"):
            gain = xp_gain_media()
        elif raw:
            gain = xp_gain(raw)
        else:
            return
        if gain <= 0:
            return
        board = _board(chat_id)
        rec = board.get(user_id)
        now = time.monotonic()
        cooldown = float(_get(api, chat_id, "xp_cooldown_s", DEFAULT_COOLDOWN_S))
        if rec is not None and now - rec["last"] < cooldown:
            return
        old_xp = rec["xp"] if rec else 0
        new_xp = old_xp + gain
        old_level = level_from_xp(old_xp)
        new_level = level_from_xp(new_xp)
        name = (str(ctx.data.get("sender_name") or ctx.user_name or user_id))[:MAX_NAME]
        board[user_id] = {"xp": new_xp, "name": name, "last": now}
        if new_level > old_level:
            # اعلام صعود سطح
            ctx.respond(api.tr(ctx.lang, "level_up", name=name, level=new_level))

    # ── /rank ───────────────────────────────────────────────────────
    async def cmd_rank(ctx):
        target = (ctx.args or "").strip()
        user_id = ctx.user_id
        if target and target.lstrip("-").isdigit():
            try:
                user_id = int(target)
            except ValueError:
                user_id = ctx.user_id
        board = _board(ctx.chat_id)
        rec = board.get(user_id)
        if rec is None:
            ctx.respond(api.tr(ctx.lang, "no_xp_yet", id=user_id))
            return
        xp = rec["xp"]
        level = level_from_xp(xp)
        prog = progress(xp)
        pct = int(prog * 100)
        ctx.respond(
            api.tr(ctx.lang, "rank",
                   name=rec["name"], id=user_id, xp=xp,
                   level=level, need=xp_to_next_level(level), pct=pct)
        )

    # ── /top ────────────────────────────────────────────────────────
    async def cmd_top(ctx):
        board = _board(ctx.chat_id)
        rows = sorted(board.items(), key=lambda kv: kv[1]["xp"], reverse=True)[:10]
        if not rows:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        lines = [api.tr(ctx.lang, "top_header", n=len(rows))]
        medals = ("🥇", "🥈", "🥉")
        for i, (uid, rec) in enumerate(rows, start=1):
            lvl = level_from_xp(rec["xp"])
            medal = medals[i - 1] if i <= 3 else f"{i}."
            name = rec["name"] or str(uid)
            lines.append(f"{medal} {name} — سطح {lvl} ({rec['xp']} XP)")
        ctx.respond("\n".join(lines))

    # ── /levels و /xpcooldown (ادمین) ───────────────────────────────
    async def cmd_levels(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "levels_on", True)
            cd = _get(api, ctx.chat_id, "xp_cooldown_s", DEFAULT_COOLDOWN_S)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, cooldown=cd))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "levels_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "levels_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_xpcooldown(ctx):
        try:
            cd = int((ctx.args or "").strip())
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_cooldown"))
            return
        if not 0 <= cd <= 3600:
            ctx.respond(api.tr(ctx.lang, "usage_cooldown"))
            return
        _put(api, ctx.chat_id, "xp_cooldown_s", cd)
        ctx.respond(api.tr(ctx.lang, "cooldown_set", cooldown=cd))

    async def cmd_resetlevels(ctx):
        _xp.pop(ctx.chat_id, None)
        ctx.respond(api.tr(ctx.lang, "reset"))

    api.register_event(EVENT_MESSAGE, on_message, priority=6)  # بعد از ضداسپم
    api.register_command("rank", cmd_rank, group_only=True, aliases=("rank", "رتبه"),
                         usage="rank [id]")
    api.register_command("top", cmd_top, group_only=True, aliases=("top", "برترین‌ها"))
    api.register_command("levels", cmd_levels, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("levels", "سطح‌بندی"), usage="levels [on|off]")
    api.register_command("xpcooldown", cmd_xpcooldown, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("xpcooldown", "مهلت امتیاز"), usage="xpcooldown <0-3600>")
    api.register_command("resetlevels", cmd_resetlevels, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("resetlevels", "صفر کردن سطح‌ها"))


def on_unload(api) -> None:
    _xp.clear()
