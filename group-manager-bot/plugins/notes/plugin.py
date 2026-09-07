"""پلاگین notes — یادداشت‌های گروهی (پاسخ‌های ذخیره‌شده).

مدیر متن بلندی را با یک نام کوتاه ذخیره می‌کند؛ هر کاربر با فرستادن «#نام» در
گروه، متنِ یادداشت را دریافت می‌کند. کاربردی برای قوانین، راهنما، لینک‌های
پرکاربرد و… نام‌ها نرمال‌سازی می‌شوند (ضد دورزدنِ جزئی).
"""

from __future__ import annotations

import re

from bot.domain.roles import AccessLevel
from bot.domain.text_normalize import normalize_text
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

MAX_LEN = 1024
MAX_NAME_LEN = 40
_HASHTAG_RE = re.compile(r"#([^\s#،؛!؟?]+)")


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


def _notes(api, chat_id) -> dict:
    return dict(_get(api, chat_id, "notes", {}))


def _norm(name: str) -> str:
    n = normalize_text(name, leet=False).strip()
    return n[:MAX_NAME_LEN]


def register(api) -> None:
    def admin_only(ctx) -> bool:
        return api.access.level(ctx.chat_id, ctx.user_id) >= AccessLevel.ADMIN

    # ── تریگر #نام ──────────────────────────────────────────────────
    async def on_message(ctx) -> None:
        chat_id = ctx.chat_id
        if chat_id is None or ctx.user_id is None:
            return
        if not api.is_enabled(chat_id):
            return
        notes = _notes(api, chat_id)
        if not notes:
            return
        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "")
        for tag in _HASHTAG_RE.findall(raw):
            name = _norm(tag)
            if name in notes:
                ctx.respond(notes[name])
                return  # فقط اولین برخورد

    # ── فرمان‌ها ────────────────────────────────────────────────────
    def list_lines(notes: dict, lang: str) -> str:
        if not notes:
            return api.tr(lang, "empty")
        names = "، ".join(f"#{n}" for n in sorted(notes))
        return api.tr(lang, "list_header", n=len(notes)) + "\n" + names

    async def cmd_note(ctx):
        parts = (ctx.args or "").split(maxsplit=2)
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        action, name_raw = parts[0].lower(), parts[1]
        name = _norm(name_raw)
        if not name:
            ctx.respond(api.tr(ctx.lang, "bad_name"))
            return
        notes = _notes(api, ctx.chat_id)
        if action in ("get", "نشان", "نمایش"):
            if name not in notes:
                ctx.respond(api.tr(ctx.lang, "not_found", name=name_raw))
                return
            ctx.respond(f"📝 {name}:\n{notes[name]}")
        elif action in ("list", "فهرست", "لیست"):
            ctx.respond(list_lines(notes, ctx.lang))
        elif action in ("save", "add", "ذخیره", "افزودن"):
            if not admin_only(ctx):
                ctx.respond(api.tr(ctx.lang, "admin_only"))
                return
            content = parts[2].strip() if len(parts) > 2 else ""
            if not content:
                ctx.respond(api.tr(ctx.lang, "usage"))
                return
            if len(content) > MAX_LEN:
                ctx.respond(api.tr(ctx.lang, "too_long", max=MAX_LEN))
                return
            notes[name] = content
            _put(api, ctx.chat_id, "notes", notes)
            ctx.respond(api.tr(ctx.lang, "saved", name=name_raw, total=len(notes)))
        elif action in ("del", "delete", "حذف"):
            if not admin_only(ctx):
                ctx.respond(api.tr(ctx.lang, "admin_only"))
                return
            if name not in notes:
                ctx.respond(api.tr(ctx.lang, "not_found", name=name_raw))
                return
            del notes[name]
            _put(api, ctx.chat_id, "notes", notes)
            ctx.respond(api.tr(ctx.lang, "deleted", name=name_raw))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_notes(ctx):
        ctx.respond(list_lines(_notes(api, ctx.chat_id), ctx.lang))

    async def cmd_savenote(ctx):
        parts = (ctx.args or "").split(maxsplit=1)
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        name = _norm(parts[0])
        content = parts[1].strip()
        if not name:
            ctx.respond(api.tr(ctx.lang, "bad_name"))
            return
        if not admin_only(ctx):
            ctx.respond(api.tr(ctx.lang, "admin_only"))
            return
        if len(content) > MAX_LEN:
            ctx.respond(api.tr(ctx.lang, "too_long", max=MAX_LEN))
            return
        notes = _notes(api, ctx.chat_id)
        notes[name] = content
        _put(api, ctx.chat_id, "notes", notes)
        ctx.respond(api.tr(ctx.lang, "saved", name=parts[0], total=len(notes)))

    async def cmd_delnote(ctx):
        name_raw = (ctx.args or "").strip()
        if not name_raw:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        if not admin_only(ctx):
            ctx.respond(api.tr(ctx.lang, "admin_only"))
            return
        name = _norm(name_raw)
        if not name:
            ctx.respond(api.tr(ctx.lang, "bad_name"))
            return
        notes = _notes(api, ctx.chat_id)
        if name not in notes:
            ctx.respond(api.tr(ctx.lang, "not_found", name=name_raw))
            return
        del notes[name]
        _put(api, ctx.chat_id, "notes", notes)
        ctx.respond(api.tr(ctx.lang, "deleted", name=name_raw))

    api.register_event(EVENT_MESSAGE, on_message, priority=8)
    api.register_command("note", cmd_note, group_only=True, aliases=("note", "یادداشت"),
                         usage="note <save|get|del|list> <name> [متن]")
    api.register_command("notes", cmd_notes, group_only=True, aliases=("notes", "یادداشت‌ها"))
    api.register_command("savenote", cmd_savenote, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("savenote", "ذخیره یادداشت"),
                         usage="savenote <name> <متن>")
    api.register_command("delnote", cmd_delnote, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("delnote", "حذف یادداشت"), usage="delnote <name>")


def on_unload(api) -> None:
    pass
