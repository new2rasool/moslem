"""پلاگین ping — بررسی سلامت ربات.

نمونهٔ ساده‌ترین پلاگین: فقط یک فرمان. برای افزودن این قابلیت هیچ تغییری در
هسته لازم نبود؛ صرفاً فایل در پوشهٔ plugins قرار گرفته است.
"""

from __future__ import annotations

import time

PLUGIN_VERSION = "1.0.0"


def register(api) -> None:
    async def ping(ctx) -> None:
        start = time.perf_counter()
        n = len(api.host.enabled_names())
        ms = round((time.perf_counter() - start) * 1000, 2)
        ctx.respond(api.tr(ctx.lang, "pong", ms=ms, plugins=n))

    api.register_command("ping", ping, aliases=("ping", "پینگ"))
