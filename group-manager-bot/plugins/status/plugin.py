"""پلاگین status — داشبورد فنی ربات.

وضعیت کلی ربات را نشان می‌دهد: زمان روشن بودن (uptime)، شمار پلاگین‌های
بارگذاری‌شده، فرمان‌ها/رویدادهای ثبت‌شده (از PluginRecordهای میزبان)، و
شمار اکشن‌های امروزِ این گروه (از دفتر حسابرسی).
"""

from __future__ import annotations

import time

from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"

_boot = time.monotonic()


def _fmt_uptime(seconds: float) -> str:
    seconds = int(seconds)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days} روز")
    if hours:
        parts.append(f"{hours} ساعت")
    if minutes:
        parts.append(f"{minutes} دقیقه")
    parts.append(f"{secs} ثانیه")
    return " ".join(parts)


def register(api) -> None:
    async def cmd_status(ctx):
        host = api.host
        records = host.records if host is not None else {}
        plugins = sorted(records)
        commands = sum(r.commands for r in records.values())
        events = sum(r.events for r in records.values())
        callbacks = sum(r.callbacks for r in records.values())
        lines = [
            api.tr(ctx.lang, "title"),
            "🤖 " + api.tr(ctx.lang, "uptime", up=_fmt_uptime(time.monotonic() - _boot)),
            "🧩 " + api.tr(ctx.lang, "plugins", n=len(plugins)),
            "⚙️ " + api.tr(ctx.lang, "commands", n=commands, events=events,
                           callbacks=callbacks),
        ]
        # اکشن‌های امروزِ همین گروه
        if ctx.chat_id is not None and api.actions is not None:
            try:
                today = api.actions.count_today(ctx.chat_id)
                lines.append("📈 " + api.tr(ctx.lang, "today", n=today))
            except Exception:  # noqa: BLE001
                pass
        lines.append("🛠 " + api.tr(ctx.lang, "plugins_list",
                                    names="، ".join(plugins)))
        ctx.respond("\n".join(lines))

    api.register_command("status", cmd_status, aliases=("status", "وضعیت ربات"),
                         usage="status")


def on_unload(api) -> None:
    pass
