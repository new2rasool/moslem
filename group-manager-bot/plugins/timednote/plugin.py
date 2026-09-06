"""پلاگین timednote — یادداشت/اعلان زمان‌دارِ یک‌باره برای گروه.

ادمین با «timednote <مدت> <متن>» یک پیام زمان‌دار ثبت می‌کند؛ on_tick میزبان
در سررسید آن را به گروه می‌فرستد و از صف حذف می‌کند (یک‌بار مصرف — برخلاف
announcer که دوره‌ای است).

محدودیت‌ها: حداکثر ۵ یادداشت همزمان در هر گروه؛ مدت بین ۱ دقیقه تا ۷ روز
(قالب domain/duration مثل «30m»، «2h»، «1d6h»). متن حداکثر ۹۰۰ نویسه.
"""

from __future__ import annotations

import time

from bot.domain.duration import DurationError, format_duration, parse_duration
from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

MAX_PER_CHAT = 5
MIN_S = 60
MAX_S = 7 * 86400
MAX_TEXT = 900

# chat_id → [{"id", "due_at", "text", "lang"}]
_jobs: dict[int, list[dict]] = {}
_next_id = 1


def _group_lang(api, chat_id) -> str:
    group = api.groups.get(chat_id)
    return group.lang if group else "fa"


def register(api) -> None:
    async def cmd_timednote(ctx):
        global _next_id
        chat_id = ctx.chat_id
        parts = (ctx.args or "").split(maxsplit=1)
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        try:
            delay = parse_duration(parts[0])
        except DurationError:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        text = parts[1].strip()
        if not (MIN_S <= delay <= MAX_S):
            ctx.respond(api.tr(ctx.lang, "range"))
            return
        if len(text) > MAX_TEXT:
            ctx.respond(api.tr(ctx.lang, "long", n=MAX_TEXT))
            return
        jobs = _jobs.setdefault(chat_id, [])
        if len(jobs) >= MAX_PER_CHAT:
            ctx.respond(api.tr(ctx.lang, "full", n=MAX_PER_CHAT))
            return
        job = {"id": _next_id, "due_at": time.monotonic() + delay,
               "text": text, "lang": ctx.lang}
        _next_id += 1
        jobs.append(job)
        ctx.respond(api.tr(ctx.lang, "scheduled", id=job["id"],
                           when=format_duration(int(delay)),
                           remaining=MAX_PER_CHAT - len(jobs)))

    # ── فهرست ───────────────────────────────────────────────────────
    async def cmd_timednotes(ctx):
        chat_id = ctx.chat_id
        jobs = _jobs.get(chat_id, [])
        if not jobs:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        lines = [api.tr(ctx.lang, "list_header")]
        for job in jobs:
            remaining = int(max(0.0, job["due_at"] - time.monotonic()))
            preview = job["text"][:50].replace("\n", " ")
            lines.append(f"#{job['id']} ⏳ {format_duration(remaining)} — {preview}")
        ctx.respond("\n".join(lines))

    # ── حذف ─────────────────────────────────────────────────────────
    async def cmd_timednotedel(ctx):
        chat_id = ctx.chat_id
        raw = (ctx.args or "").strip()
        if not raw.isdigit():
            ctx.respond(api.tr(ctx.lang, "usage_del"))
            return
        jobs = _jobs.get(chat_id, [])
        wanted = int(raw)
        for i, job in enumerate(jobs):
            if job["id"] == wanted:
                jobs.pop(i)
                ctx.respond(api.tr(ctx.lang, "removed", id=wanted))
                return
        ctx.respond(api.tr(ctx.lang, "not_found", id=wanted))

    api.register_command("timednote", cmd_timednote, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("timednote", "اعلان زمان‌دار"),
                         usage="timednote <30m|2h|1d> <متن>")
    api.register_command("timednotes", cmd_timednotes,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("timednotes", "یادداشت‌های زمان‌دار"),
                         usage="timednotes")
    api.register_command("timednotedel", cmd_timednotedel,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("timednotedel",),
                         usage="timednotedel <id>")


async def on_tick(api) -> None:
    """تحویل یادداشت‌های سررسیدشده (از میزبان)."""
    now = time.monotonic()
    for chat_id, jobs in list(_jobs.items()):
        due = [j for j in jobs if j["due_at"] <= now]
        if not due:
            continue
        rest = [j for j in jobs if j["due_at"] > now]
        if rest:
            _jobs[chat_id] = rest
        else:
            _jobs.pop(chat_id, None)
        for job in due:
            api.host.send_text(chat_id, api.tr(job["lang"], "delivered",
                                               text=job["text"]))


def on_unload(api) -> None:
    _jobs.clear()
