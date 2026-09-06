"""پلاگین faq — پرسش‌های پرتکرارِ گروه با دکمه‌های شیشه‌ای.

ادمین با «faqadd پرسش => پاسخ» سؤال ثبت می‌کند؛ هر عضو با «faq» فهرستِ
دکمه‌ای پرسش‌ها را می‌بیند و با کلیک پاسخ را می‌خواند. پرسش‌های تکراری
(نرمال‌شده) رد می‌شوند و فهرست بلند صفحه‌بندی می‌شود.

داده در تنظیمات گروه (کلید faq_items) می‌ماند: فهرستی از
{"q": str, "a": str}. سقف: ۳۰ پرسش؛ هر پرسش ۱۲۰ نویسه؛ هر پاسخ ۱۰۰۰ نویسه.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel
from bot.domain.text_normalize import normalize_text

PLUGIN_VERSION = "1.0.0"

MAX_ITEMS = 30
MAX_Q = 120
MAX_A = 1000
PAGE_SIZE = 10

# کلید دکمه‌ها: faq:<chat>:a:<idx> پاسخ · faq:<chat>:list فهرست
#                            · faq:<chat>:p:<page> صفحهٔ بعد


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


def _items(api, chat_id) -> list[dict]:
    return list(_get(api, chat_id, "faq_items", []) or [])


def _save(api, chat_id, items: list[dict]) -> None:
    _put(api, chat_id, "faq_items", items)


def _answer_buttons(api, chat_id: int, index: int) -> list[list[dict]]:
    return [[{"text": "⬅️ بازگشت به فهرست",
              "data": f"faq:{chat_id}:list"}]]


def register(api) -> None:
    # ── نمایش فهرست دکمه‌ای ──────────────────────────────────────────
    def _list_buttons(chat_id: int, page: int) -> list[list[dict]]:
        items = _items(api, chat_id)
        start = page * PAGE_SIZE
        chunk = items[start:start + PAGE_SIZE]
        buttons: list[list[dict]] = []
        for i, item in enumerate(chunk):
            idx = start + i
            q = str(item.get("q", ""))
            label = f"{idx + 1}. {q}"[:40]
            buttons.append([{"text": label,
                             "data": f"faq:{chat_id}:a:{idx}"}])
        if len(items) > (page + 1) * PAGE_SIZE:
            buttons.append([{"text": "⏭ صفحهٔ بعد",
                             "data": f"faq:{chat_id}:p:{page + 1}"}])
        return buttons

    async def cmd_faq(ctx):
        chat_id = ctx.chat_id
        items = _items(api, chat_id)
        if not items:
            if api.access.level(chat_id, ctx.user_id) >= AccessLevel.ADMIN:
                ctx.respond(api.tr(ctx.lang, "empty_admin",
                                   usage="faqadd پرسش => پاسخ"))
            else:
                ctx.respond(api.tr(ctx.lang, "empty"))
            return
        ctx.respond_buttons(api.tr(ctx.lang, "list", n=len(items)),
                            _list_buttons(chat_id, 0))

    # ── افزودن ──────────────────────────────────────────────────────
    async def cmd_faqadd(ctx):
        chat_id = ctx.chat_id
        if "=>" not in ctx.args:
            ctx.respond(api.tr(ctx.lang, "usage_add"))
            return
        q, _, a = ctx.args.partition("=>")
        q = q.strip()
        a = a.strip()
        if not q or not a:
            ctx.respond(api.tr(ctx.lang, "usage_add"))
            return
        if len(q) > MAX_Q or len(a) > MAX_A:
            ctx.respond(api.tr(ctx.lang, "too_long", q=MAX_Q, a=MAX_A))
            return
        items = _items(api, chat_id)
        if len(items) >= MAX_ITEMS:
            ctx.respond(api.tr(ctx.lang, "full", n=MAX_ITEMS))
            return
        norm = normalize_text(q)
        if any(normalize_text(str(i.get("q", ""))) == norm for i in items):
            ctx.respond(api.tr(ctx.lang, "dup"))
            return
        items.append({"q": q, "a": a})
        _save(api, chat_id, items)
        ctx.respond(api.tr(ctx.lang, "added", n=len(items), q=q))

    # ── حذف ─────────────────────────────────────────────────────────
    async def cmd_faqdel(ctx):
        chat_id = ctx.chat_id
        raw = (ctx.args or "").strip()
        if raw == "all":
            _save(api, chat_id, [])
            ctx.respond(api.tr(ctx.lang, "cleared"))
            return
        items = _items(api, chat_id)
        if not items:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        if not raw:
            # فهرست شماره‌دار برای انتخاب
            lines = [api.tr(ctx.lang, "pick")]
            for idx, item in enumerate(items):
                lines.append(f"{idx + 1}. {item.get('q', '')}")
            ctx.respond("\n".join(lines))
            return
        if not raw.isdigit():
            ctx.respond(api.tr(ctx.lang, "usage_del"))
            return
        idx = int(raw) - 1
        if not (0 <= idx < len(items)):
            ctx.respond(api.tr(ctx.lang, "bad_index"))
            return
        removed = items.pop(idx)
        _save(api, chat_id, items)
        ctx.respond(api.tr(ctx.lang, "removed", q=removed.get("q", "")))

    # ── پاسخ دکمه‌ها ────────────────────────────────────────────────
    async def on_answer(ctx) -> None:
        parts = ctx.payload.split(":")
        if len(parts) < 2:
            return
        try:
            chat_id = int(parts[0])
        except ValueError:
            return
        if chat_id != ctx.chat_id:
            ctx.respond(api.tr(ctx.lang, "stale"))
            return
        kind = parts[1]
        items = _items(api, chat_id)
        if kind == "a" and len(parts) >= 3 and parts[2].isdigit():
            idx = int(parts[2])
            if not (0 <= idx < len(items)):
                ctx.respond(api.tr(ctx.lang, "stale"))
                return
            item = items[idx]
            ctx.respond_buttons(
                api.tr(ctx.lang, "answer", q=item.get("q", ""),
                       a=item.get("a", "")),
                _answer_buttons(api, chat_id, idx),
            )
        elif kind == "list":
            if not items:
                ctx.respond(api.tr(ctx.lang, "empty"))
                return
            ctx.respond_buttons(api.tr(ctx.lang, "list", n=len(items)),
                                _list_buttons(chat_id, 0))
        elif kind == "p" and len(parts) >= 3 and parts[2].isdigit():
            page = int(parts[2])
            start = page * PAGE_SIZE
            if not items or start >= len(items):
                ctx.respond(api.tr(ctx.lang, "stale"))
                return
            chunk = items[start:start + PAGE_SIZE]
            buttons = []
            for i, item in enumerate(chunk):
                idx = start + i
                buttons.append([{"text": f"{idx + 1}. "
                                         f"{str(item.get('q', ''))[:40]}",
                                 "data": f"faq:{chat_id}:a:{idx}"}])
            if len(items) > (page + 1) * PAGE_SIZE:
                buttons.append([{"text": "⏭ صفحهٔ بعد",
                                 "data": f"faq:{chat_id}:p:{page + 1}"}])
            ctx.respond_buttons(api.tr(ctx.lang, "list", n=len(items)),
                                buttons)

    api.register_callback("faq:", on_answer)
    api.register_command("faq", cmd_faq, group_only=True,
                         aliases=("faq", "سوالات متداول"),
                         usage="faq")
    api.register_command("faqadd", cmd_faqadd, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("faqadd",),
                         usage="faqadd <پرسش> => <پاسخ>")
    api.register_command("faqdel", cmd_faqdel, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("faqdel",),
                         usage="faqdel [شماره|all]")


def on_unload(api) -> None:
    pass
