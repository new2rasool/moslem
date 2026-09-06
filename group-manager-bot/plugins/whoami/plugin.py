"""پلاگین whoami — نمایش هویت و سطح دسترسی کاربر.

نمایش استفاده از سرویس access هسته از داخل پلاگین (سطح مؤثر کاربر).
"""

from __future__ import annotations

from bot.domain.roles import LEVEL_LABELS_EN, LEVEL_LABELS_FA

PLUGIN_VERSION = "1.0.0"


def register(api) -> None:
    async def whoami(ctx) -> None:
        level = api.access.level(ctx.chat_id, ctx.user_id)
        labels = LEVEL_LABELS_FA if ctx.lang == "fa" else LEVEL_LABELS_EN
        group_line = ""
        if ctx.chat_id and not ctx.is_private:
            group_line = api.tr(
                ctx.lang, "group_line", chat=ctx.sender_name or ctx.chat_id, chat_id=ctx.chat_id
            )
        ctx.respond(
            api.tr(
                ctx.lang,
                "whoami_out",
                name=ctx.sender_name or api.tr(ctx.lang, "anonymous"),
                id=ctx.user_id,
                username=ctx.sender_username or "—",
                level=labels.get(level, level.name),
                group_line=group_line,
            )
        )

    async def show_id(ctx) -> None:
        lines = [api.tr(ctx.lang, "your_id", id=ctx.user_id)]
        if ctx.chat_id and not ctx.is_private:
            lines.append(api.tr(ctx.lang, "chat_id", id=ctx.chat_id))
        ctx.respond("\n".join(lines))

    api.register_command("whoami", whoami, aliases=("whoami", "من"))
    api.register_command("id", show_id, aliases=("id", "آیدی"))
