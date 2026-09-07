"""پلاگین capsguard — گارد نوشتن با حروف بزرگ و تکرار نویسه.

دو تخلف را در پیام اعضای عادی می‌گیرد (کارکنان معاف):
  1) «جیغ زدن»: اگر بخش لاتین متن ≥ حداقل نویسه باشد و نسبت حروف بزرگ آن
     ≥ ۷۵٪ باشد (مثل «HELLO WORLD این یک پیام است») → حذف + هشدار.
  2) تکرارِ یک نویسه پشت‌سرهم به‌اندازهٔ آستانه یا بیشتر (مثل «خخخخخخخ» یا
     «!!!!!!») → حذف + هشدار.
هشدار برای هر کاربر هر ۳۰ ثانیه یک‌بار. ساعت/تنظیمات تزریق‌پذیر برای تست.
"""

from __future__ import annotations

import re
import time

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

WARN_COOLDOWN_S = 30.0
_last_warn: dict[tuple[int, int], float] = {}


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


_LATIN_RE = re.compile(r"[A-Za-z]")


def _is_shouting(text: str, min_latin: int, ratio: float) -> bool:
    letters = _LATIN_RE.findall(text)
    if len(letters) < min_latin:
        return False
    upper = sum(1 for ch in letters if ch.isupper())
    return upper / len(letters) >= ratio


def _max_run(text: str) -> int:
    """بلندترین رشتهٔ تکراریِ پشت‌سرهم یک نویسه (غیر از فاصله)."""
    best = run = 0
    prev = ""
    for ch in text:
        if ch == prev and not ch.isspace():
            run += 1
        else:
            run = 1
        prev = ch
        if run > best:
            best = run
    return best


def register(api) -> None:
    async def on_message(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "caps_on", False):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        raw = str(ctx.data.get("text") or ctx.data.get("caption") or "").strip()
        if not raw:
            return
        min_latin = int(_get(api, chat_id, "caps_min_latin", 6))
        ratio = 0.75
        min_run = int(_get(api, chat_id, "caps_min_run", 6))
        if not (_is_shouting(raw, min_latin, ratio)
                or _max_run(raw) >= min_run):
            return
        now = time.monotonic()
        warn_key = (chat_id, user_id)
        last = _last_warn.get(warn_key)
        if last is None or now - last >= WARN_COOLDOWN_S:
            _last_warn[warn_key] = now
            ctx.act("delete_message", user_id=user_id, reason="caps")
            ctx.respond(api.tr(ctx.lang, "warn", user=user_id))
        else:
            ctx.act("delete_message", user_id=user_id, reason="caps")

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_capsguard(ctx):
        parts = (ctx.args or "").split()
        if not parts:
            on = _get(api, ctx.chat_id, "caps_on", False)
            ml = _get(api, ctx.chat_id, "caps_min_latin", 6)
            mr = _get(api, ctx.chat_id, "caps_min_run", 6)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st, latin=ml, run=mr))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "caps_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "caps_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_setcaps(ctx):
        parts = (ctx.args or "").split()
        if len(parts) < 2:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        try:
            ml = int(parts[0])
            mr = int(parts[1])
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        if not (3 <= ml <= 30) or not (3 <= mr <= 20):
            ctx.respond(api.tr(ctx.lang, "usage_set"))
            return
        _put(api, ctx.chat_id, "caps_min_latin", ml)
        _put(api, ctx.chat_id, "caps_min_run", mr)
        ctx.respond(api.tr(ctx.lang, "set_ok", latin=ml, run=mr))

    api.register_event(EVENT_MESSAGE, on_message, priority=240)
    api.register_command("capsguard", cmd_capsguard, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("capsguard",),
                         usage="capsguard [on|off]")
    api.register_command("setcaps", cmd_setcaps, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("setcaps",),
                         usage="setcaps <min_latin 3-30> <min_run 3-20>")


def on_unload(api) -> None:
    _last_warn.clear()
