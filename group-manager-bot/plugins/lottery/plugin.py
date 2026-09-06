"""پلاگین lottery — قرعه‌کشی گروهی با دکمهٔ شرکت.

ادمین «lottery start» می‌زند؛ اعضای عادی با دکمهٔ «🎟 شرکت در قرعه‌کشی» در آن
ثبت می‌شوند (هر عضو فقط یک بار). ادمین با «lottery end» برنده را شفاف انتخاب
و اعلام می‌کند (یا با «lottery cancel» لغو). فقط یک قرعه‌کشی همزمان در هر گروه.
"""

from __future__ import annotations

import random

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

# chat_id → {"creator", "entries": [{"id","name"}]}
_lotteries: dict[int, dict] = {}


def register(api) -> None:
    async def cmd_lottery(ctx):
        chat_id = ctx.chat_id
        cmd = (ctx.args or "").strip().lower()
        if cmd in ("start", "شروع"):
            if chat_id in _lotteries:
                ctx.respond(api.tr(ctx.lang, "already"))
                return
            _lotteries[chat_id] = {"creator": ctx.user_id, "entries": []}
            ctx.respond_buttons(
                api.tr(ctx.lang, "started", user=ctx.user_id),
                [[{"text": "🎟 شرکت در قرعه‌کشی", "data": f"lot:{chat_id}:join"}]],
            )
        elif cmd in ("end", "پایان"):
            game = _lotteries.get(chat_id)
            if game is None:
                ctx.respond(api.tr(ctx.lang, "none"))
                return
            entries = game["entries"]
            if not entries:
                _lotteries.pop(chat_id, None)
                ctx.respond(api.tr(ctx.lang, "no_entries"))
                return
            winner = random.choice(entries)
            _lotteries.pop(chat_id, None)
            ctx.respond(api.tr(ctx.lang, "winner", name=winner["name"],
                               user=winner["id"], n=len(entries)))
        elif cmd in ("cancel", "لغو"):
            if chat_id not in _lotteries:
                ctx.respond(api.tr(ctx.lang, "none"))
                return
            _lotteries.pop(chat_id, None)
            ctx.respond(api.tr(ctx.lang, "cancelled"))
        elif cmd in ("status", "وضعیت"):
            game = _lotteries.get(chat_id)
            if game is None:
                ctx.respond(api.tr(ctx.lang, "none"))
                return
            ctx.respond(api.tr(ctx.lang, "status_text", n=len(game["entries"])))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    # ── شرکت (دکمه) ─────────────────────────────────────────────────
    async def on_join(ctx) -> None:
        parts = ctx.payload.split(":")
        if len(parts) < 2:
            return
        try:
            chat_id = int(parts[0])
        except ValueError:
            return
        game = _lotteries.get(chat_id)
        if game is None:
            ctx.respond(api.tr(ctx.lang, "closed"))
            return
        if ctx.user_id == game["creator"]:
            ctx.respond(api.tr(ctx.lang, "no_creator"))
            return
        if api.access.level(chat_id, ctx.user_id) >= AccessLevel.ADMIN:
            ctx.respond(api.tr(ctx.lang, "no_staff"))
            return
        if any(e["id"] == ctx.user_id for e in game["entries"]):
            ctx.respond(api.tr(ctx.lang, "already_in"))
            return
        name = (ctx.sender_name or str(ctx.user_id))[:24]
        game["entries"].append({"id": ctx.user_id, "name": name})
        ctx.respond(api.tr(ctx.lang, "joined", n=len(game["entries"])))

    api.register_callback("lot:", on_join)
    api.register_command("lottery", cmd_lottery, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("lottery", "قرعه‌کشی"),
                         usage="lottery <start|end|cancel|status>")


def on_unload(api) -> None:
    _lotteries.clear()
