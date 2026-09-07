"""پلاگین polls — نظرسنجی تعاملی گروه با دکمه‌های شیشه‌ای.

ادمین با /poll «سؤال | گزینه۱ | گزینه۲ | …» نظرسنجی می‌سازد؛ گزینه‌ها به‌صورت
دکمه ارسال می‌شوند و هر عضو فقط یک بار رأی می‌دهد. نتایج زنده با pollresults و
پایان با pollclose. در هر گروه فقط یک نظرسنجیِ فعال وجود دارد.
"""

from __future__ import annotations

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

MAX_OPTS = 9
MIN_OPTS = 2
TTL_S = 24 * 3600


def _key(chat_id: int) -> str:
    return f"poll:active:{chat_id}"


def register(api) -> None:
    def render(poll: dict, lang: str) -> str:
        lines = [f"📊 {poll['q']}"]
        for i, opt in enumerate(poll["opts"], start=1):
            lines.append(f"{i}) {opt} — {poll['counts'][i - 1]} رأی")
        lines.append(api.tr(lang, "total", n=poll["total"]))
        return "\n".join(lines)

    # ── ساخت (ادمین) ────────────────────────────────────────────────
    async def cmd_poll(ctx):
        parts = (ctx.args or "").split("|")
        if len(parts) < MIN_OPTS + 1:
            ctx.respond(api.tr(ctx.lang, "usage", mn=MIN_OPTS, mx=MAX_OPTS))
            return
        question = parts[0].strip()
        opts = [p.strip() for p in parts[1:]][:MAX_OPTS]
        if len(opts) < MIN_OPTS or not question or len(question) > 200:
            ctx.respond(api.tr(ctx.lang, "bad"))
            return
        if any(not o or len(o) > 80 for o in opts):
            ctx.respond(api.tr(ctx.lang, "bad_opt"))
            return
        old = api.cache.get(_key(ctx.chat_id))
        pid = (old.get("pid", 0) + 1) if old else 1
        poll = {
            "pid": pid,
            "q": question,
            "opts": opts,
            "counts": [0] * len(opts),
            "voters": [],
            "creator": ctx.user_id,
            "total": 0,
        }
        api.cache.set(_key(ctx.chat_id), poll, ttl_s=TTL_S)
        # دکمه‌های رأی (هر ردیف ۲ گزینه)
        buttons = []
        for i in range(0, len(opts), 2):
            row = [{"text": f"{j + 1}) {opts[j][:24]}",
                    "data": f"poll:{pid}:{j}"} for j in range(i, min(i + 2, len(opts)))]
            buttons.append(row)
        ctx.respond_buttons(api.tr(ctx.lang, "created", n=len(opts)) + "\n📊 " + question,
                            buttons)

    # ── رأی (دکمه) ──────────────────────────────────────────────────
    async def on_vote(ctx) -> None:
        parts = ctx.payload.split(":")
        if len(parts) < 2:
            return
        try:
            pid, idx = int(parts[0]), int(parts[1])
        except ValueError:
            return
        key = _key(ctx.chat_id)
        poll = api.cache.get(key)
        if poll is None or poll["pid"] != pid:
            ctx.respond(api.tr(ctx.lang, "closed"))
            return
        if idx < 0 or idx >= len(poll["opts"]):
            return
        if ctx.user_id in poll["voters"]:
            ctx.respond(api.tr(ctx.lang, "already", opt=poll["opts"][idx]))
            return
        poll["counts"][idx] += 1
        poll["total"] += 1
        poll["voters"].append(ctx.user_id)
        api.cache.set(key, poll, ttl_s=TTL_S)
        ctx.respond(api.tr(ctx.lang, "voted", opt=poll["opts"][idx],
                           total=poll["total"]))

    # ── نتیجه / پایان ───────────────────────────────────────────────
    async def cmd_pollresults(ctx):
        poll = api.cache.get(_key(ctx.chat_id))
        if poll is None:
            ctx.respond(api.tr(ctx.lang, "none"))
            return
        ctx.respond(render(poll, ctx.lang))

    async def cmd_pollclose(ctx):
        key = _key(ctx.chat_id)
        poll = api.cache.get(key)
        if poll is None:
            ctx.respond(api.tr(ctx.lang, "none"))
            return
        api.cache.delete(key)
        winner_i = max(range(len(poll["counts"])), key=lambda i: poll["counts"][i])
        lines = [render(poll, ctx.lang), "—",
                 api.tr(ctx.lang, "winner", opt=poll["opts"][winner_i],
                        n=poll["counts"][winner_i])]
        ctx.respond("\n".join(lines))

    api.register_callback("poll:", on_vote)
    api.register_command("poll", cmd_poll, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("poll", "نظرسنجی"),
                         usage="poll <سؤال | گزینه۱ | گزینه۲ | …>")
    api.register_command("pollresults", cmd_pollresults, group_only=True,
                         aliases=("pollresults", "نتایج نظرسنجی"))
    api.register_command("pollclose", cmd_pollclose, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("pollclose", "پایان نظرسنجی"))


def on_unload(api) -> None:
    pass
