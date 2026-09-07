"""پلاگین admin_utils — ابزارهای مدیران (نمونهٔ چک سطح دسترسی).

فرمان «duration» فقط برای سطح MOD به بالا در دسترس است؛ هسته سطح دسترسی را
بر اساس نقشِ ثبت‌شدهٔ کاربر چک می‌کند و بقیه پیام «دسترسی ندارید» می‌گیرند.
"""

from __future__ import annotations

from bot.domain.duration import DurationError, format_duration, parse_duration
from bot.domain.roles import AccessLevel

PLUGIN_VERSION = "1.0.0"


def register(api) -> None:
    async def duration(ctx) -> None:
        if not ctx.args:
            ctx.respond(api.tr(ctx.lang, "usage"))
            return
        try:
            seconds = parse_duration(ctx.args)
        except DurationError:
            ctx.respond(api.tr(ctx.lang, "invalid", raw=ctx.args))
            return
        ctx.respond(
            api.tr(
                ctx.lang,
                "result",
                raw=ctx.args,
                seconds=seconds,
                human=format_duration(seconds),
            )
        )

    api.register_command(
        "duration",
        duration,
        level=AccessLevel.MOD,
        aliases=("duration", "مدت", "زمان"),
        usage="duration <مدت>   مثل: duration 1d6h30m",
    )
