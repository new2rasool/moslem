"""پلاگین trivia — مسابقهٔ گروهی (سؤال‌وجواب با امتیاز).

ادمین «quiz on» می‌زند → سؤال اول (از بانک داخلی) پرسیده می‌شود؛ هر عضو با
«answer <شماره>» (یا «پاسخ») شرکت می‌کند. نخستین پاسخِ درست ۱ امتیاز می‌گیرد
و سؤال بعدی پس از GAP ثانیه خودکار پرسیده می‌شود (on_tick). اگر کسی در
مهلت پاسخ ندهد، جواب اعلام و سؤال بعدی برنامه‌ریزی می‌شود. پاسخِ غلط پیام
«غلط» می‌گیرد بدون افشای جواب (بقیه فرصت دارند). «score» جدول امتیازهاست.
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

QUESTION_S = 120.0   # مهلت هر سؤال
GAP_S = 12.0         # فاصله بین دو سؤال

# بانک سؤال (fa): متن، ۴ گزینه، اندیس پاسخِ درست
_BANK = [
    {"q": "پایتخت فرانسه کدام است؟",
     "opts": ["پاریس", "لیون", "مارسی", "نیس"], "a": 0},
    {"q": "زبان برنامه‌نویسیِ این ربات چیست؟",
     "opts": ["پایتون", "جاوا", "سی‌شارپ", "روبی"], "a": 0},
    {"q": "کدام سیاره به خورشید نزدیک‌تر است؟",
     "opts": ["زهره", "عطارد", "زمین", "مریخ"], "a": 1},
    {"q": "حاصل ۱۲ × ۱۲ کدام است؟",
     "opts": ["۱۲۴", "۱۴۴", "۱۵۴", "۱۲۲"], "a": 1},
    {"q": "مصر در کدام قاره قرار دارد؟",
     "opts": ["آسیا", "آفریقا", "اروپا", "آمریکای جنوبی"], "a": 1},
]

# chat_id → وضعیت بازی
_games: dict[int, dict] = {}

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")


def _new_game() -> dict:
    return {
        "on": True, "qno": 0, "qi": 0, "open": False, "deadline": 0.0,
        "next_at": 0.0, "scores": {}, "names": {}, "answered": {},
    }


def _question_text(api, lang: str, g: dict) -> str:
    item = _BANK[g["qi"] % len(_BANK)]
    lines = [api.tr(lang, "question_title", n=g["qno"] + 1), "❓ " + item["q"]]
    for i, opt in enumerate(item["opts"], start=1):
        lines.append(f"{i}) {opt}")
    lines.append(api.tr(lang, "howto"))
    return "\n".join(lines)


def _reveal_text(api, lang: str, g: dict) -> str:
    item = _BANK[g["qi"] % len(_BANK)]
    return api.tr(lang, "timeout_reveal", answer=f"{item['a'] + 1}) {item['opts'][item['a']]}")


def register(api) -> None:
    def post_question(ctx_or_lang, g: dict, chat_id: int | None = None) -> None:
        """پرسیدنِ سؤال جاری: در بافت فرمان با respond، در تیک با send_text."""
        lang = ctx_or_lang if isinstance(ctx_or_lang, str) else ctx_or_lang.lang
        g["qno"] += 1
        g["open"] = True
        g["deadline"] = time.monotonic() + QUESTION_S
        g["next_at"] = 0.0
        g["answered"] = {}
        text = _question_text(api, lang, g)
        if isinstance(ctx_or_lang, str):
            api.host.send_text(chat_id, text)
        else:
            ctx_or_lang.respond(text)

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_quiz(ctx):
        parts = (ctx.args or "").split()
        cmd = parts[0].lower() if parts else ""
        chat = ctx.chat_id
        if cmd in ("on", "روشن"):
            if chat in _games and _games[chat]["on"]:
                ctx.respond(api.tr(ctx.lang, "already_on"))
                return
            g = _new_game()
            _games[chat] = g
            ctx.respond(api.tr(ctx.lang, "started"))
            post_question(ctx, g)
        elif cmd in ("off", "خاموش"):
            if chat in _games:
                del _games[chat]
                ctx.respond(api.tr(ctx.lang, "stopped"))
            else:
                ctx.respond(api.tr(ctx.lang, "not_running"))
        elif cmd in ("next", "بعدی"):
            g = _games.get(chat)
            if g is None or not g["on"]:
                ctx.respond(api.tr(ctx.lang, "not_running"))
                return
            if g["open"]:
                ctx.respond(api.tr(ctx.lang, "still_open"))
                return
            g["qi"] = (g["qi"] + 1) % len(_BANK)
            post_question(ctx, g)
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_answer(ctx):
        chat = ctx.chat_id
        g = _games.get(chat) if chat is not None else None
        if g is None or not g["on"]:
            ctx.respond(api.tr(ctx.lang, "not_running"))
            return
        if not g["open"]:
            ctx.respond(api.tr(ctx.lang, "wait_next"))
            return
        raw = (ctx.args or "").strip().translate(_PERSIAN_DIGITS)
        if not raw.isdigit():
            ctx.respond(api.tr(ctx.lang, "usage_answer"))
            return
        choice = int(raw)
        item = _BANK[g["qi"] % len(_BANK)]
        if not (1 <= choice <= len(item["opts"])):
            ctx.respond(api.tr(ctx.lang, "usage_answer"))
            return
        if ctx.user_id in g["answered"]:
            ctx.respond(api.tr(ctx.lang, "already_answered"))
            return
        if choice - 1 == item["a"]:
            # نخستین پاسخِ درست این سؤال → امتیاز
            name = (ctx.sender_name or str(ctx.user_id))[:24]
            g["names"].setdefault(ctx.user_id, name)
            g["scores"][ctx.user_id] = g["scores"].get(ctx.user_id, 0) + 1
            g["answered"][ctx.user_id] = name
            g["open"] = False
            g["next_at"] = time.monotonic() + GAP_S
            total = g["scores"][ctx.user_id]
            ctx.respond(api.tr(ctx.lang, "correct", name=name, total=total))
        else:
            ctx.respond(api.tr(ctx.lang, "wrong"))

    async def cmd_score(ctx):
        g = _games.get(ctx.chat_id)
        if g is None or not g["on"] or not g["scores"]:
            ctx.respond(api.tr(ctx.lang, "no_scores"))
            return
        lines = [api.tr(ctx.lang, "score_header")]
        for rank, (uid, pts) in enumerate(
                sorted(g["scores"].items(), key=lambda kv: -kv[1])[:10], start=1):
            name = g["names"].get(uid, uid)
            lines.append(f"{rank}. {name} — {pts}")
        ctx.respond("\n".join(lines))

    api.register_command("quiz", cmd_quiz, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("quiz", "مسابقه"), usage="quiz <on|off|next>")
    api.register_command("answer", cmd_answer, group_only=True,
                         aliases=("answer", "پاسخ"), usage="answer <1-4>")
    api.register_command("score", cmd_score, group_only=True,
                         aliases=("score", "امتیازها"))


async def on_tick(api) -> None:
    """چرخ خودکار مسابقه: سؤال بعدی / اعلام پایان مهلت."""
    now = time.monotonic()
    for chat_id, g in list(_games.items()):
        group = api.groups.get(chat_id)
        lang = group.lang if group is not None else "fa"
        if g["open"]:
            if now >= g["deadline"]:
                api.host.send_text(chat_id, _reveal_text(api, lang, g))
                g["open"] = False
                g["next_at"] = now + GAP_S
        elif now >= g["next_at"]:
            # سؤال بعدی (round-robin در بانک)
            g["qi"] = (g["qi"] + 1) % len(_BANK)
            g["qno"] += 1
            g["open"] = True
            g["deadline"] = now + QUESTION_S
            g["next_at"] = 0.0
            g["answered"] = {}
            api.host.send_text(chat_id, _question_text(api, lang, g))


def on_unload(api) -> None:
    _games.clear()
