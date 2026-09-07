"""پلاگین mediafocus — حالت «فقط رسانه» برای گروه‌های اطلاع‌رسانی/مدیا.

وقتی روشن باشد، اعضای عادی فقط می‌توانند رسانه بفرستند (عکس/ویدیو/گیف/سند/
ویس/وویس‌نوت/استیکر/صدا)؛ پیامِ متنیِ بدونِ رسانه حذف و هشدارِ محدود (هر ۳۰
ثانیه) فرستاده می‌شود. با «mediafocus caption off» کپشنِ روی رسانه هم ممنوع
می‌شود (فقط خودِ رسانه بدون متن).

کارکنان و فرمان‌ها معاف‌اند. اجرا روی رویداد message با اولویت ۲۶۰
(پس از antirepeat/capsguard و پیش از واکنش‌های آمار/سطح).
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MESSAGE

PLUGIN_VERSION = "1.0.0"

MEDIA_TYPES = {"photo", "video", "animation", "document", "voice",
               "video_note", "sticker", "audio"}
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


def register(api) -> None:
    async def on_message(ctx) -> None:
        chat_id, user_id = ctx.chat_id, ctx.user_id
        if chat_id is None or user_id is None or user_id < 0:
            return
        if not api.is_enabled(chat_id):
            return
        if not _get(api, chat_id, "mfoc_on", False):
            return
        if api.access.level(chat_id, user_id) >= AccessLevel.MOD:
            return
        data = ctx.data or {}
        ctype = str(data.get("content_type") or "text")
        text = str(data.get("text") or "").strip()
        allow_caption = bool(_get(api, chat_id, "mfoc_allow_caption", True))

        is_media = ctype in MEDIA_TYPES
        if is_media:
            if allow_caption or not text:
                return  # رسانه مجاز است (با کپشن اگر مجاز باشد)
        # نقض: یا متن بدون رسانه، یا کپشنِ غیرمجاز
        ctx.act("delete_message", user_id=user_id, reason="mediafocus")
        key = (chat_id, user_id)
        now = time.monotonic()
        last = _last_warn.get(key)
        if last is None or now - last >= WARN_COOLDOWN_S:
            _last_warn[key] = now
            if is_media:
                ctx.respond(api.tr(ctx.lang, "warn_caption"))
            else:
                ctx.respond(api.tr(ctx.lang, "warn_text",
                                   user=user_id))

    # ── فرمان‌ها ─────────────────────────────────────────────────────
    async def cmd_mediafocus(ctx):
        parts = (ctx.args or "").split()
        cmd = parts[0].lower() if parts else ""
        if cmd in ("on", "روشن"):
            _put(api, ctx.chat_id, "mfoc_on", True)
            ctx.respond(api.tr(ctx.lang, "enabled"))
        elif cmd in ("off", "خاموش"):
            _put(api, ctx.chat_id, "mfoc_on", False)
            ctx.respond(api.tr(ctx.lang, "disabled"))
        elif cmd == "caption" and len(parts) > 1:
            sub = parts[1].lower()
            if sub in ("on", "روشن"):
                _put(api, ctx.chat_id, "mfoc_allow_caption", True)
                ctx.respond(api.tr(ctx.lang, "caption_on"))
            elif sub in ("off", "خاموش"):
                _put(api, ctx.chat_id, "mfoc_allow_caption", False)
                ctx.respond(api.tr(ctx.lang, "caption_off"))
            else:
                ctx.respond(api.tr(ctx.lang, "usage_caption"))
        else:
            on = _get(api, ctx.chat_id, "mfoc_on", False)
            cap = _get(api, ctx.chat_id, "mfoc_allow_caption", True)
            st = api.tr(ctx.lang, "on") if on else api.tr(ctx.lang, "off")
            cap_st = api.tr(ctx.lang, "on") if cap else api.tr(ctx.lang, "off")
            ctx.respond(api.tr(ctx.lang, "status", state=st,
                               caption=cap_st))

    api.register_event(EVENT_MESSAGE, on_message, priority=260)
    api.register_command("mediafocus", cmd_mediafocus,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("mediafocus", "فقط رسانه"),
                         usage="mediafocus [on|off|caption <on|off>]")


def on_unload(api) -> None:
    _last_warn.clear()
