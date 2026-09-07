"""پلاگین digest — گزارش دوره‌ای خودکار گروه (به کانال لاگ یا خودِ گروه).

ادمین با «digest <دقیقه>» گزارش دوره‌ای را روشن می‌کند؛ on_tick میزبان در
هر دوره یک خلاصه (اکشن‌های امروز از دفتر، ورود/خروجِ دوره، وضعیت محافظت‌ها)
می‌سازد و به کانال لاگ (کلید log_channel که پلاگین audit می‌نویسد) و اگر
تنظیم نشده به خودِ گروه می‌فرستد. «digest off» متوقف می‌کند.
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel
from bot.registry import EVENT_MEMBER_JOINED, EVENT_MEMBER_LEFT

PLUGIN_VERSION = "1.0.0"

MIN_MIN = 10
MAX_MIN = 1440

# chat_id → {"interval_s", "last_sent", "since": زمان شروع دورهٔ بعدی}
_jobs: dict[int, dict] = {}
_day_joins: dict[int, int] = {}
_day_leaves: dict[int, int] = {}


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
    async def cmd_digest(ctx):
        chat_id = ctx.chat_id
        raw = (ctx.args or "").strip().lower()
        if raw in ("off", "خاموش"):
            _jobs.pop(chat_id, None)
            ctx.respond(api.tr(ctx.lang, "disabled"))
            return
        try:
            minutes = int(raw)
        except ValueError:
            ctx.respond(api.tr(ctx.lang, "usage", mn=MIN_MIN, mx=MAX_MIN))
            return
        if not MIN_MIN <= minutes <= MAX_MIN:
            ctx.respond(api.tr(ctx.lang, "usage", mn=MIN_MIN, mx=MAX_MIN))
            return
        _jobs[chat_id] = {"interval_s": minutes * 60, "last_sent": 0.0}
        channel = _get(api, chat_id, "log_channel", "")
        dest = api.tr(ctx.lang, "to_channel", ch=channel) if channel \
            else api.tr(ctx.lang, "to_group")
        ctx.respond(api.tr(ctx.lang, "enabled", minutes=minutes) + "\n" + dest)

    api.register_command("digest", cmd_digest, level=AccessLevel.ADMIN,
                         group_only=True, aliases=("digest", "گزارش دوره‌ای"),
                         usage=f"digest <دقیقه {MIN_MIN}-{MAX_MIN}|off>")

    # ── شمارندهٔ ورود/خروج بین دو گزارش ─────────────────────────────
    async def on_joined(ctx) -> None:
        if ctx.chat_id is not None and _jobs.get(ctx.chat_id):
            _day_joins[ctx.chat_id] = _day_joins.get(ctx.chat_id, 0) + 1

    async def on_left(ctx) -> None:
        if ctx.chat_id is not None and _jobs.get(ctx.chat_id):
            _day_leaves[ctx.chat_id] = _day_leaves.get(ctx.chat_id, 0) + 1

    api.register_event(EVENT_MEMBER_JOINED, on_joined, priority=5)
    api.register_event(EVENT_MEMBER_LEFT, on_left, priority=5)


async def on_tick(api) -> None:
    """ساخت و ارسال گزارش‌های سررسیدشده (از میزبان)."""
    now = time.monotonic()
    for chat_id, job in list(_jobs.items()):
        if now - job["last_sent"] < job["interval_s"]:
            continue
        job["last_sent"] = now
        group = api.groups.get(chat_id)
        lang = group.lang if group is not None else "fa"
        lines = [api.tr(lang, "title", chat=chat_id)]
        # اکشن‌های امروز از دفتر حسابرسی
        if api.actions is not None:
            try:
                today = api.actions.count_today(chat_id)
                lines.append("📈 " + api.tr(lang, "actions", n=today))
            except Exception:  # noqa: BLE001
                pass
        joins = _day_joins.pop(chat_id, 0)
        leaves = _day_leaves.pop(chat_id, 0)
        lines.append("👥 " + api.tr(lang, "joins", n=joins, m=leaves))
        # وضعیت محافظت‌های اصلی
        guards = []
        for key, label in (("captcha_on", "کپچا"), ("ja_on", "تأیید ورود"),
                           ("flood_on", "ضد سیل"), ("wg_on", "کلمات ممنوع"),
                           ("automod_on", "تشدید خودکار")):
            g = group.settings.get(key) if group is not None else None
            if g is True:
                guards.append(label)
        if guards:
            lines.append("🛡 " + api.tr(lang, "guards", names="، ".join(guards)))
        text = "\n".join(lines)
        channel = group.settings.get("log_channel", "") if group is not None else ""
        dest = _parse_channel(channel)
        api.host.send_text(dest if dest is not None else chat_id, text)


def _parse_channel(channel: str) -> int | None:
    """پشتیبانی از «-100123…» و «100123…»؛ @channel نیاز به resolve دارد ← None."""
    ch = (channel or "").strip()
    if not ch:
        return None
    try:
        return int(ch)
    except ValueError:
        return None


def on_unload(api) -> None:
    _jobs.clear()
