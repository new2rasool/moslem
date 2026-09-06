"""پلاگین greeter — خوش‌آمد به عضو جدید (نمونهٔ رویدادمحور).

این پلاگین به رویداد «عضو جدید» گوش می‌دهد و پیام خوش‌آمد می‌فرستد. متن
خوش‌آمد را می‌توان با کلید `greet_text` در تنظیمات گروه بازنویسی کرد.
"""

from __future__ import annotations

from bot.registry import EVENT_MEMBER_JOINED

PLUGIN_VERSION = "1.0.0"


def register(api) -> None:
    async def on_member_joined(ctx) -> None:
        chat_id = ctx.chat_id
        name = ctx.data.get("member_name") or ctx.user_name or api.tr(ctx.lang, "dear")
        # اولویت با متن سفارشی گروه است (خواندن از تنظیمات گروه از طریق repo)
        text = None
        if chat_id:
            group = api.groups.get(chat_id)
            if group:
                text = group.settings.get("greet_text")
        if not text:
            text = api.tr(ctx.lang, "welcome_default")
        # جایگزینی امن (بدون خطا روی بریس‌های ناخواستهٔ متن سفارشی)
        text = (
            text.replace("{name}", name)
            .replace("{chat}", str(ctx.data.get("chat_title", "")))
            .replace("{username}", str(ctx.data.get("member_username", "")))
        )
        ctx.respond(text)

    api.register_event(EVENT_MEMBER_JOINED, on_member_joined, priority=50)
