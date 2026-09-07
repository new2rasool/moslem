"""پلاگین globalguard — کلمات ممنوع سراسری (چندگروهی، مشترک بین همهٔ گروه‌ها).

فهرست کلمات (نرمال‌شدهٔ ضد دورزدن) در کش میزبان نگهداری می‌شود؛ هر پیامی که
شامل یکی از آن‌ها باشد در هر گروه حذف و هشدار داده می‌شود. فقط مالک ربات
(SUDO) می‌تواند کلمه اضافه/حذف کند — برای هماهنگی بین گروه‌ها.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel
from bot.domain.text_normalize import normalize_text
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

KEY = "gg:words"
TTL_S = 30 * 24 * 3600  # ۳۰ روز
MIN_WORD = 3


def _all(api) -> list:
    return list(api.cache.get(KEY) or [])


def register(api) -> None:
    async def on_message(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        words = _all(api)
        if not words:
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        if not raw:
            return
        norm = normalize_text(raw, leet=True)
        hit = next((w for w in words if w and w in norm), None)
        if hit is None:
            return
        ctx.act("delete_message", user_id=user_id, reason=f"gg:{hit}")
        ctx.respond(api.tr(ctx.lang, "warn", user=user_id))

    # ── فرمان‌ها (فقط SUDO) ─────────────────────────────────────────
    async def cmd_ggadd(ctx):
        word = (ctx.args or "").strip()
        norm = normalize_text(word, leet=True).strip()
        if len(norm) < MIN_WORD:
            ctx.respond(api.tr(ctx.lang, "too_short", min=MIN_WORD))
            return
        words = _all(api)
        if norm in words:
            ctx.respond(api.tr(ctx.lang, "already", word=word))
            return
        words.append(norm)
        api.cache.set(KEY, words, ttl_s=TTL_S)
        ctx.respond(api.tr(ctx.lang, "added", word=word, n=len(words)))

    async def cmd_ggdel(ctx):
        word = (ctx.args or "").strip()
        norm = normalize_text(word, leet=True).strip()
        words = _all(api)
        if norm not in words:
            ctx.respond(api.tr(ctx.lang, "not_found", word=word))
            return
        words = [w for w in words if w != norm]
        api.cache.set(KEY, words, ttl_s=TTL_S)
        ctx.respond(api.tr(ctx.lang, "removed", word=word, n=len(words)))

    async def cmd_gglist(ctx):
        words = _all(api)
        if not words:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        ctx.respond(api.tr(ctx.lang, "header", n=len(words)) + "\n" +
                    "، ".join(words))

    api.register_event(EVENT_MESSAGE, on_message, priority=270)
    api.register_command("ggadd", cmd_ggadd, level=AccessLevel.SUDO,
                         aliases=("ggadd",), usage="ggadd <کلمه>")
    api.register_command("ggdel", cmd_ggdel, level=AccessLevel.SUDO,
                         aliases=("ggdel",), usage="ggdel <کلمه>")
    api.register_command("gglist", cmd_gglist, level=AccessLevel.SUDO,
                         aliases=("gglist",))


def on_unload(api) -> None:
    pass
