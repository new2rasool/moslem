"""پلاگین captcha — احراز هویت ضدربات هنگام ورود عضو (نسخهٔ پیشرفته).

- به رویداد member_joined گوش می‌دهد؛ اگر عضو تازه از CAPTCHA معاف نیست، یک
  پرسش جمع با دکمه‌های شیشه‌ای می‌فرستد و با اکشن restrict او را محدود می‌کند.
- پاسخ‌ها از callback («captcha:...») می‌آیند؛ پاسخ درست → unrestrict؛
  پاسخ غلط → تلاش بعدی؛ اتمام تلاش‌ها/مهلت → kick (از طریق action_sink).
- مهلت با on_tick میزبان بررسی و اخراج خودکار انجام می‌شود (بدون وابستگی به کاربر).
"""

from __future__ import annotations

import time

from bot.domain.captcha import generate, verify
from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED

PLUGIN_VERSION = "1.0.0"

MAX_TRIES = 3
CHALLENGE_TTL_BUF = 5  # ثانیهٔ اضافه روی TTL کش


def _setting(api, chat_id, key, default):
    g = api.groups.get(chat_id)
    return g.settings.get(key, default) if g else default


def _put(api, chat_id, key, value):
    from bot.repositories.base import Group

    g = api.groups.get(chat_id)
    if g is None:
        g = Group(chat_id=chat_id, settings={})
    g.settings[key] = value
    api.groups.upsert(g)


def _key(chat_id: int, user_id: int) -> str:
    return f"captcha:{chat_id}:{user_id}"


# چالش‌های در انتظار: (chat,user) → وضعیت (برای on_tick مهلت‌سنج)
_pending: dict[tuple[int, int], dict] = {}


def register(api) -> None:
    # ── رویداد ورود عضو ─────────────────────────────────────────────
    async def on_join(ctx) -> None:
        chat_id = ctx.chat_id
        user_id = ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _setting(api, chat_id, "captcha_on", False):
            return
        # ادمین‌ها/مدیران نیازی به کپچا ندارند
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return

        time_s = int(_setting(api, chat_id, "captcha_time_s", 60))
        q, answer, options = generate()
        # ذخیرهٔ وضعیت چالش (در cache + یک رجیستری ماژولی برای on_tick)
        state = {"answer": answer, "tries": 0, "deadline": time.monotonic() + time_s}
        api.cache.set(_key(chat_id, user_id), state, ttl_s=time_s + CHALLENGE_TTL_BUF)
        _pending[(chat_id, user_id)] = state

        # دکمه‌ها: گزینه‌های عددی + دکمهٔ «انصراف/اخراج من»؟
        buttons = [
            [{"text": str(opt), "data": f"captcha:{chat_id}:{user_id}:{opt}"} for opt in options[:2]],
            [{"text": str(opt), "data": f"captcha:{chat_id}:{user_id}:{opt}"} for opt in options[2:]],
        ]
        ctx.respond_buttons(api.tr(ctx.lang, "question", user=user_id), buttons)
        # محدودسازی عضو تا پاسخ (اجرای فیزیکی با آداپتور)
        ctx.act("restrict", user_id=user_id, reason="captcha:pending")

    # ── پاسخ دکمه ───────────────────────────────────────────────────
    async def on_answer(ctx) -> None:
        # payload: chat:user:answer
        parts = ctx.payload.split(":")
        if len(parts) < 3:
            return
        try:
            chat_id, user_id, given = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return
        state = api.cache.get(_key(chat_id, user_id))
        if state is None:
            ctx.respond(api.tr(ctx.lang, "none_pending"))
            return

        if time.monotonic() > state["deadline"]:
            api.cache.delete(_key(chat_id, user_id))
            _pending.pop((chat_id, user_id), None)
            ctx.respond(api.tr(ctx.lang, "expired"))
            ctx.act("kick", user_id=user_id, reason="captcha:timeout")
            return

        if verify(int(state["answer"]), given):
            api.cache.delete(_key(chat_id, user_id))
            _pending.pop((chat_id, user_id), None)
            ctx.respond(api.tr(ctx.lang, "passed"))
            ctx.act("unrestrict", user_id=user_id, reason="captcha:passed")
        else:
            state["tries"] += 1
            if state["tries"] >= MAX_TRIES:
                api.cache.delete(_key(chat_id, user_id))
                _pending.pop((chat_id, user_id), None)
                ctx.respond(api.tr(ctx.lang, "failed"))
                ctx.act("kick", user_id=user_id, reason="captcha:failed")
            else:
                api.cache.set(_key(chat_id, user_id), state, ttl_s=60)
                ctx.respond(api.tr(ctx.lang, "wrong", tries=state["tries"], max=MAX_TRIES))

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_captcha(ctx):
        parts = ctx.args.split()
        if not parts:
            on = _setting(api, ctx.chat_id, "captcha_on", False)
            t = _setting(api, ctx.chat_id, "captcha_time_s", 60)
            state = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=state, time=t))
            return
        if parts[0].lower() in ("on", "روشن"):
            _put(api, ctx.chat_id, "captcha_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif parts[0].lower() in ("off", "خاموش"):
            _put(api, ctx.chat_id, "captcha_on", False)
            _pending.clear()  # چالش‌های در انتظار لغو شد
            ctx.respond(api.tr(ctx.lang, "disabled"))
        else:
            ctx.respond(api.tr(ctx.lang, "usage"))

    async def cmd_settime(ctx):
        try:
            t = int((ctx.args or "").strip())
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage_time"))
            return
        if not 10 <= t <= 300:
            ctx.respond(api.tr(ctx.lang, "usage_time"))
            return
        _put(api, ctx.chat_id, "captcha_time_s", t)
        ctx.respond(api.tr(ctx.lang, "time_set", t=t))

    # ثبت‌ها
    api.register_event(EVENT_MEMBER_JOINED, on_join, priority=400)
    api.register_callback("captcha:", on_answer)
    api.register_command("captcha", cmd_captcha, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("captcha", "کپچا"), usage="captcha [on|off]")
    api.register_command("setcaptchatime", cmd_settime, level=AccessLevel.ADMIN, group_only=True,
                         aliases=("setcaptchatime", "تنظیم مهلت کپچا"), usage="setcaptchatime <10-300>")


async def on_tick(api) -> None:
    """مهلت‌سنج — از میزبان هر ~۲ ثانیه صدا زده می‌شود؛ چالش‌های منقضی را اخراج می‌کند."""
    now = time.monotonic()
    expired = [(k, st) for k, st in _pending.items() if st["deadline"] <= now]
    for (chat_id, user_id), _st in expired:
        api.cache.delete(_key(chat_id, user_id))
        _pending.pop((chat_id, user_id), None)
        api.host.send_text(chat_id, api.tr("fa", "expired_kick", user=user_id))
        api.host.push_action(chat_id, {"type": "kick", "user_id": user_id, "reason": "captcha:timeout"})


def on_unload(api) -> None:
    """پاک‌سازی چالش‌های معلق هنگام حذف/ری‌لود پلاگین."""
    _pending.clear()
