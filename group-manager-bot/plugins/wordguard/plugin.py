"""پلاگین wordguard — فیلتر کلمات/عبارات سیاه گروه (ضد اسپم متنی).

متن هر پیام ابتدا با domain/text_normalize نرمال می‌شود (ضد دورزدن: فاصلهٔ
کاذب، تکرار حرف، حروف عربی…) و سپس برابر هر کلمهٔ سیاهِ گروه چک می‌شود.
اکشن‌ها: delete (پیش‌فرض، حذف بی‌صدا) یا warn (حذف + پیام هشدار).
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel
from bot.domain.text_normalize import normalize_text
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


def _hit_word(normalized: str, words: list[str]) -> str | None:
    """اولین کلمهٔ سیاهی که زیررشتهٔ متن نرمال‌شده است."""
    for w in words:
        if w and w in normalized:
            return w
    return None


def register(api) -> None:
    async def on_message(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None or ctx.user_id is None or ctx.user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "wg_on", True):
            return
        level = api.access.level(chat_id, ctx.user_id)
        if level >= AccessLevel.ADMIN:
            return

        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        if not raw:
            return
        words = list(_get(api, chat_id, "bl_words", []))
        if not words:
            return

        norm = normalize_text(raw, leet=True)
        hit = _hit_word(norm, words)
        if hit is None:
            return

        ctx.act("delete_message", reason=f"blacklist:{hit}", user_id=ctx.user_id)
        mode = _get(api, chat_id, "wg_mode", "delete")
        if mode == "warn":
            ctx.respond(api.tr(ctx.lang, "warned", word=hit, user=ctx.user_id))

    # ── فرمان‌ها ────────────────────────────────────────────────────
    async def cmd_add(ctx):
        parts = ctx.args.split()
        if not parts:
            ctx.respond(api.tr(ctx.lang, "usage_add"))
            return
        words = set(_get(api, ctx.chat_id, "bl_words", []))
        added = 0
        for token in parts:
            norm = normalize_text(token, leet=True)
            if norm and norm not in words:
                words.add(norm)
                added += 1
        _put(api, ctx.chat_id, "bl_words", sorted(words))
        _put(api, ctx.chat_id, "wg_on", True)
        ctx.respond(api.tr(ctx.lang, "added", n=added, total=len(words)))

    async def cmd_rm(ctx):
        parts = ctx.args.split()
        if not parts:
            ctx.respond(api.tr(ctx.lang, "usage_rm"))
            return
        words = set(_get(api, ctx.chat_id, "bl_words", []))
        before = len(words)
        for token in parts:
            words.discard(normalize_text(token, leet=True))
        _put(api, ctx.chat_id, "bl_words", sorted(words))
        ctx.respond(api.tr(ctx.lang, "removed", n=before - len(words), total=len(words)))

    async def cmd_list(ctx):
        words = _get(api, ctx.chat_id, "bl_words", [])
        mode = _get(api, ctx.chat_id, "wg_mode", "delete")
        on = _get(api, ctx.chat_id, "wg_on", True)
        state = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
        lines = [api.tr(ctx.lang, "header", state=state, mode=mode)]
        if words:
            for i, w in enumerate(words, 1):
                lines.append(f"{i}. {w}")
        else:
            lines.append(api.tr(ctx.lang, "empty"))
        ctx.respond("\n".join(lines))

    async def cmd_mode(ctx):
        val = (ctx.args or "").strip().lower()
        if val in ("delete", "حذف"):
            _put(api, ctx.chat_id, "wg_mode", "delete")
            ctx.respond(api.tr(ctx.lang, "mode_delete"))
        elif val in ("warn", "هشدار"):
            _put(api, ctx.chat_id, "wg_mode", "warn")
            ctx.respond(api.tr(ctx.lang, "mode_warn"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage_mode"))

    api.register_event(EVENT_MESSAGE, on_message, priority=250)
    api.register_command("addblacklist", cmd_add, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("addblacklist", "افزودن کلمه سیاه"), usage="addblacklist <word...>")
    api.register_command("rmblacklist", cmd_rm, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("rmblacklist", "حذف کلمه سیاه"))
    api.register_command("blacklists", cmd_list, group_only=True,
                         aliases=("blacklists", "کلمات سیاه"))
    api.register_command("blacklistmode", cmd_mode, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("blacklistmode", "حالت فیلتر"), usage="blacklistmode <delete|warn>")
