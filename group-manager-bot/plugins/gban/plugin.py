"""پلاگین gban — ممنوعیت سراسری کاربر در همهٔ گروه‌ها (چندگروهی).

فهرست سیاه سراسری در کش میزبان نگهداری می‌شود (مشترک بین همهٔ گروه‌ها)؛
هر کاربری که به فهرست اضافه شود، از هر گروهی که به آن بپیوندد فوراً بن
می‌شود (رویداد member_joined با بالاترین اولویت). فقط مالک ربات (SUDO) حق
gban/ungban دارد. هر بن سراسری در دفتر حسابرسی همان گروه هم ثبت می‌شود.
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED

PLUGIN_VERSION = "1.0.0"

KEY = "gban:list"
TTL_S = 30 * 24 * 3600  # ۳۰ روز


def _all(api) -> dict:
    return dict(api.cache.get(KEY) or {})


def register(api) -> None:
    # ── بن فوری هنگام ورود ──────────────────────────────────────────
    async def on_join(ctx) -> None:
        chat_id = ctx.chat_id
        user_id = ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        entry = _all(api).get(user_id)
        if entry is None:
            return
        # بن سراسری فوری (قبل از هر پلاگین دیگری مثل کپچا)
        ctx.respond(api.tr(ctx.lang, "join_denied", user=user_id))
        ctx.act("ban", user_id=user_id, reason=f"gban: {entry.get('reason', '')}")
        await api.record_action(chat_id, "auto:gban", user_id, 0,
                                reason=f"gban: {entry.get('reason', '')}")

    # ── فرمان‌ها (فقط SUDO) ─────────────────────────────────────────
    async def cmd_gban(ctx):
        parts = (ctx.args or "").strip().split(maxsplit=1)
        if len(parts) < 2 or not parts[0].lstrip("-").isdigit():
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        user_id = int(parts[0])
        reason = parts[1].strip()[:120]
        if user_id <= 0:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        if api.access.is_bot_owner(user_id) or user_id in api.cfg.sudo_ids:
            ctx.respond(api.tr(ctx.lang, "no_owner"))
            return
        store = _all(api)
        if user_id in store:
            ctx.respond(api.tr(ctx.lang, "already", user=user_id))
            return
        store[user_id] = {"reason": reason, "by": ctx.user_id,
                          "at": time.strftime("%Y-%m-%d %H:%M")}
        api.cache.set(KEY, store, ttl_s=TTL_S)
        if ctx.chat_id is not None:  # ثبت در دفتر حسابرسی گروه جاری
            await api.record_action(ctx.chat_id, "gban", user_id, ctx.user_id,
                                    reason=f"gban: {reason}")
        ctx.respond(api.tr(ctx.lang, "done", user=user_id, reason=reason))

    async def cmd_ungban(ctx):
        target = (ctx.args or "").strip()
        if not target.lstrip("-").isdigit():
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        user_id = int(target)
        store = _all(api)
        if user_id not in store:
            ctx.respond(api.tr(ctx.lang, "not_in_list", user=user_id))
            return
        del store[user_id]
        api.cache.set(KEY, store, ttl_s=TTL_S)
        ctx.respond(api.tr(ctx.lang, "removed", user=user_id))

    async def cmd_gbanlist(ctx):
        store = _all(api)
        if not store:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        lines = [api.tr(ctx.lang, "header", n=len(store))]
        for uid, e in sorted(store.items()):
            lines.append(f"• {uid} — {e.get('reason') or '—'} (توسط {e.get('by')}) {e.get('at', '')}")
        ctx.respond("\n".join(lines))

    api.register_event(EVENT_MEMBER_JOINED, on_join, priority=600)
    api.register_command("gban", cmd_gban, level=AccessLevel.SUDO,
                         aliases=("gban", "بن سراسری"), usage="gban <id> <دلیل>")
    api.register_command("ungban", cmd_ungban, level=AccessLevel.SUDO,
                         aliases=("ungban", "رفع بن سراسری"), usage="ungban <id>")
    api.register_command("gbanlist", cmd_gbanlist, level=AccessLevel.SUDO,
                         aliases=("gbanlist", "فهرست بن سراسری"))


def on_unload(api) -> None:
    pass
