"""پلاگین announcer — اعلان‌های دوره‌ای خودکار گروه.

مدیر پیام‌هایی با دورهٔ مشخص (دقیقه) ثبت می‌کند؛ on_tick میزبان آن‌ها را سر
وقت به گروه می‌فرستد (send_text → out_sink). برای یادآوری قوانین، دعوت به
فعالیت، نوبت‌دهی و… کاربرد دارد.

جزئیات: هر گروه چند اعلان مستقل با شناسهٔ خود دارد؛ تغییرِ یک اعلان روی بقیه
اثر نمی‌گذارد؛ خاموش‌کردن پلاگین همهٔ زمان‌بندی‌ها را نگه می‌دارد (فقط متوقف).
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

MIN_INTERVAL_MIN = 1
MAX_INTERVAL_MIN = 10080  # یک هفته
MAX_TEXT = 500

# chat_id → {id: {"text":…, "interval_s": float, "last_sent": float}}
_jobs: dict[int, dict[int, dict]] = {}
_counter: dict[int, int] = {}


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


def _texts(api, chat_id) -> list[dict]:
    return [dict(j) for j in _get(api, chat_id, "announce_texts", [])]


def register(api) -> None:
    async def cmd_announce(ctx):
        chat_id = ctx.chat_id
        parts = (ctx.args or "").partition("|")
        minutes_raw = parts[0].strip()
        text = parts[2].strip()
        try:
            minutes = float(minutes_raw)
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        if not (MIN_INTERVAL_MIN <= minutes <= MAX_INTERVAL_MIN):
            ctx.respond(api.tr(ctx.lang, "bad_interval", mn=MIN_INTERVAL_MIN,
                               mx=MAX_INTERVAL_MIN))
            return
        if not text or len(text) > MAX_TEXT:
            ctx.respond(api.tr(ctx.lang, "bad_text", max=MAX_TEXT))
            return
        _counter[chat_id] = _counter.get(chat_id, 0) + 1
        aid = _counter[chat_id]
        interval_s = minutes * 60
        _jobs.setdefault(chat_id, {})[aid] = {
            "text": text, "interval_s": interval_s, "last_sent": 0.0,
        }
        # نسخهٔ متنی هم در تنظیمات گروه نگه داشته می‌شود (بازیابی/نمایش)
        texts = _texts(api, chat_id)
        texts.append({"id": aid, "text": text, "interval_s": interval_s})
        _put(api, chat_id, "announce_texts", texts)
        ctx.respond(api.tr(ctx.lang, "added", id=aid, minutes=int(minutes)))

    async def cmd_announces(ctx):
        jobs = _jobs.get(ctx.chat_id, {})
        if not jobs:
            ctx.respond(api.tr(ctx.lang, "empty"))
            return
        lines = [api.tr(ctx.lang, "header", n=len(jobs))]
        for aid, j in sorted(jobs.items()):
            lines.append(f"#{aid} — هر {int(j['interval_s'] // 60)} دقیقه:\n{j['text'][:70]}")
        ctx.respond("\n".join(lines))

    async def cmd_announcedel(ctx):
        raw = (ctx.args or "").strip()
        if not raw.isdigit():
            ctx.respond(api.tr(ctx.lang, "usage_del"))
            return
        aid = int(raw)
        jobs = _jobs.get(ctx.chat_id, {})
        if aid not in jobs:
            ctx.respond(api.tr(ctx.lang, "not_found", id=aid))
            return
        del jobs[aid]
        texts = [t for t in _texts(api, ctx.chat_id) if t.get("id") != aid]
        _put(api, ctx.chat_id, "announce_texts", texts)
        ctx.respond(api.tr(ctx.lang, "deleted", id=aid))

    async def cmd_announceclear(ctx):
        _jobs.pop(ctx.chat_id, None)
        _put(api, ctx.chat_id, "announce_texts", [])
        ctx.respond(api.tr(ctx.lang, "cleared"))

    api.register_command("announce", cmd_announce, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("announce", "اعلان"),
                         usage="announce <دوره به دقیقه> | <متن>")
    api.register_command("announces", cmd_announces, group_only=True,
                         aliases=("announces", "اعلان‌ها"))
    api.register_command("announcedel", cmd_announcedel, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("announcedel",),
                         usage="announcedel <id>")
    api.register_command("announceclear", cmd_announceclear,
                         level=AccessLevel.ADMIN, group_only=True,
                         aliases=("announceclear",))


async def on_tick(api) -> None:
    """ارسال اعلان‌های سررسیدشده (از میزبان)."""
    now = time.monotonic()
    for chat_id, jobs in list(_jobs.items()):
        for aid, j in list(jobs.items()):
            if now - j["last_sent"] < j["interval_s"]:
                continue
            j["last_sent"] = now
            api.host.send_text(chat_id, "📢 " + j["text"])


def on_unload(api) -> None:
    _jobs.clear()
