"""پلاگین votekick — رأی‌گیری دموکراتیک برای اخراج عضو (دکمه‌ای).

هر عضوِ عادی می‌تواند «votekick <id> [دلیل]» بزند؛ یک پیام با دکمه‌های
«👍 اخراج شود / 👎 بماند» به گروه می‌رود و اعضای عادی رأی می‌دهند (هر عضو
یک رأی). در پایان مهلت (۱۲۰ ثانیه، با on_tick) اگر «موافق ≥ حد نصاب و بیشتر
از مخالف» باشد → اخراج + ثبت در دفتر؛ وگرنه رأی‌گیری بی‌نتیجه اعلام می‌شود.

ضد سوءاستفاده: هدف نمی‌تواند کارکن/مالک/ربات باشد؛ هر گروه فقط یک رأی‌گیری
همزمان؛ فاصلهٔ ۱۰ دقیقه بین دو رأی‌گیریِ هر گروه.
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

VOTE_S = 120.0
COOLDOWN_S = 600.0
DEFAULT_MIN_VOTES = 3

# chat_id → رأی‌گیری فعال
_votes: dict[int, dict] = {}
_last: dict[int, float] = {}


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


def register(api) -> None:
    async def cmd_votekick(ctx):
        chat_id = ctx.chat_id
        parts = (ctx.args or "").split(maxsplit=1)
        if len(parts) < 1 or not parts[0].lstrip("-").isdigit():
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        target = int(parts[0])
        reason = (parts[1] if len(parts) > 1 else "").strip()[:100]
        if target <= 0:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        if ctx.user_id == target:
            ctx.respond(api.tr(ctx.lang, "no_self"))
            return
        if api.access.level(chat_id, target) >= AccessLevel.MOD:
            ctx.respond(api.tr(ctx.lang, "staff_target"))
            return
        if chat_id in _votes:
            ctx.respond(api.tr(ctx.lang, "already_running"))
            return
        now = time.monotonic()
        if now - _last.get(chat_id, 0.0) < COOLDOWN_S:
            ctx.respond(api.tr(ctx.lang, "cooldown", s=int(COOLDOWN_S)))
            return
        _votes[chat_id] = {
            "target": target,
            "reason": reason,
            "proposer": ctx.user_id,
            "deadline": now + VOTE_S,
            "yes": [],
            "no": [],
        }
        ctx.respond_buttons(
            api.tr(ctx.lang, "proposed", user=target, reason=reason or "—"),
            [
                [{"text": "👍 اخراج شود", "data": f"vk:{chat_id}:{target}:y"},
                 {"text": "👎 بماند", "data": f"vk:{chat_id}:{target}:n"}],
            ],
        )

    # ── رأی (دکمه) ──────────────────────────────────────────────────
    async def on_vote(ctx) -> None:
        parts = ctx.payload.split(":")
        if len(parts) < 3:
            return
        try:
            chat_id, target, choice = int(parts[0]), int(parts[1]), parts[2]
        except ValueError:
            return
        vote = _votes.get(chat_id)
        if vote is None or vote["target"] != target:
            ctx.respond(api.tr(ctx.lang, "finished"))
            return
        if ctx.user_id == target or ctx.user_id == vote["proposer"]:
            ctx.respond(api.tr(ctx.lang, "no_vote"))
            return
        if api.access.level(chat_id, ctx.user_id) >= AccessLevel.MOD:
            ctx.respond(api.tr(ctx.lang, "staff_no_vote"))
            return
        bucket = vote["yes"] if choice == "y" else vote["no"]
        other = vote["no"] if choice == "y" else vote["yes"]
        if ctx.user_id in bucket or ctx.user_id in other:
            ctx.respond(api.tr(ctx.lang, "already_voted"))
            return
        bucket.append(ctx.user_id)
        ctx.respond(api.tr(ctx.lang, "voted", yes=len(vote["yes"]),
                           no=len(vote["no"])))

    # ── فرمان مدیر ──────────────────────────────────────────────────
    async def cmd_setvotekick(ctx):
        try:
            minimum = int((ctx.args or "").strip())
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_min"))
            return
        if not 2 <= minimum <= 20:
            ctx.respond(api.tr(ctx.lang, "usage_min"))
            return
        _put(api, ctx.chat_id, "vk_min_votes", minimum)
        ctx.respond(api.tr(ctx.lang, "min_set", n=minimum))

    api.register_callback("vk:", on_vote)
    api.register_command("votekick", cmd_votekick, group_only=True,
                         aliases=("votekick",), usage="votekick <id> [دلیل]")
    api.register_command("setvotekick", cmd_setvotekick,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setvotekick",),
                         usage="setvotekick <حد نصاب 2-20>")


async def on_tick(api) -> None:
    """پایان مهلت رأی‌گیری‌ها (از میزبان): شمارش و تصمیم."""
    now = time.monotonic()
    for chat_id, v in list(_votes.items()):
        if v["deadline"] > now:
            continue
        _votes.pop(chat_id, None)
        _last[chat_id] = now
        yes, no = len(v["yes"]), len(v["no"])
        minimum = int(_get(api, chat_id, "vk_min_votes", DEFAULT_MIN_VOTES))
        passed = yes >= minimum and yes > no
        if passed:
            api.host.send_text(chat_id, api.tr("fa", "result_pass", user=v["target"],
                                               yes=yes, no=no))
            api.host.push_action(chat_id, {"type": "kick", "user_id": v["target"],
                                           "reason": f"votekick:{v['reason']}"})
            await api.record_action(chat_id, "auto:kick", v["target"], 0,
                                    reason=f"votekick {v['reason']}".strip())
        else:
            api.host.send_text(chat_id, api.tr("fa", "result_fail", user=v["target"],
                                               yes=yes, no=no, need=minimum))


def on_unload(api) -> None:
    _votes.clear()
